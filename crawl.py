import traceback
from time import sleep
from itertools import repeat
from multiprocessing import Pool, RawValue
from typing import Any, Dict, List, Optional, Tuple
from argparse import ArgumentParser, Namespace

import numpy as np
import pandas as pd
from selenium import webdriver


NAVER_SHOPPING_CATALOG_URL = 'https://search.shopping.naver.com/catalog'
XPATH_PRODUCT_NAME = '/html/body/div/div/div[2]/div[2]/div[1]/h2'
XPATH_NUM_REVIEW = '/html/body/div/div/div[2]/div[2]/div[2]/div[3]/div[1]/ul/li[3]/a/em'
XPATH_REVIEW_SECTION = '/html/body/div/div/div[2]/div[2]/div[2]/div[3]/div[5]'
XPATH_SORT_BUTTON_RECENT = f'{XPATH_REVIEW_SECTION}/div[2]/div[1]/div[1]/a[2]'
XPATH_PAGINATION = f'{XPATH_REVIEW_SECTION}/div[3]'
XPATH_REVIEW_ITEMS = f'{XPATH_REVIEW_SECTION}/ul/li'


chromedriver_wait_time = RawValue('i', 4)


def run(args: Namespace, page_index: int) -> List[Dict[str, Any]]:
    while True:
        try:
            print(f'Crawling page {page_index}/{args.max_page}.')
            return _run(args, page_index)
        except KeyboardInterrupt:
            traceback.print_exc()
            return []
        except:
            traceback.print_exc()
            print(f'Exception from page index {page_index}.')
            chromedriver_wait_time.value += 1
            print(f'chromedriver wait_time is increased to {chromedriver_wait_time.value}.')


def _run(args: Namespace, page_index: int) -> List[Dict[str, Any]]:
    chromedriver = open_chromedriver(args.chromedriver_path)
    try:
        chromedriver.get(f'{NAVER_SHOPPING_CATALOG_URL}/{args.catalog_id}')
        sleep(2)
        if args.sort_with == 'recent':
            chromedriver.find_element_by_xpath(XPATH_SORT_BUTTON_RECENT).click()
            sleep(1)
        goto_page(chromedriver, page_index)
        return crawl_review_items(chromedriver)
    finally:
        chromedriver.quit()


def goto_page(chromedriver: webdriver.Chrome, page_index: int) -> None:
    pagination = chromedriver.find_element_by_xpath(XPATH_PAGINATION)
    if page_index < 11:
        pagination.find_element_by_xpath(f'./a[{page_index}]').click()
    else:
        for i in range((page_index - 1) // 10):
            if i == 0:
                pagination.find_element_by_xpath(f'./a[11]').click()
            else:
                pagination.find_element_by_xpath(f'./a[12]').click()
            sleep(1)
        if (page_index - 1) % 10 > 1:
            pagination.find_element_by_xpath(f'./a[{page_index % 10 + 1}]').click()


def crawl_review_items(chromedriver: webdriver.Chrome) -> List[Dict[str, Any]]:
    items = []
    sleep(2)
    review_items = chromedriver.find_elements_by_xpath(XPATH_REVIEW_ITEMS)
    assert len(review_items) == 20
    for item in review_items:
        star = int(item.find_element_by_xpath('./div[1]/span[1]').text.replace('평점', ''))
        date = item.find_element_by_xpath(f'./div[1]/span[4]').text
        review = item.find_element_by_xpath('./div[2]/div[1]').text
        items.append({'star': star, 'date': date, 'review': review})
    return items


def run_all(args: Namespace, page_numbers: List[int]) -> pd.DataFrame:
    with Pool(args.cpu_count) as pool:
        item_list = \
            [it for items in pool.starmap(run, zip(repeat(args), page_numbers)) for it in items]
    return pd.DataFrame(item_list, index=np.arange(len(item_list)))


def get_info() -> Tuple[str, int]:
    chromedriver = open_chromedriver(args.chromedriver_path)
    chromedriver.get(f'{NAVER_SHOPPING_CATALOG_URL}/{args.catalog_id}')
    product_name = chromedriver.find_element_by_xpath(XPATH_PRODUCT_NAME).text
    num_review = int(chromedriver.find_element_by_xpath(XPATH_NUM_REVIEW).text.replace(',', ''))
    chromedriver.quit()
    return product_name, num_review


def open_chromedriver(chromedriver_path: Optional[str]) -> webdriver.Chrome:
    if chromedriver_path:
        chromedriver = webdriver.Chrome(chromedriver_path)
    else:
        chromedriver = webdriver.Chrome()
    chromedriver.minimize_window()
    chromedriver.implicitly_wait(chromedriver_wait_time.value)
    return chromedriver


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument('catalog_id', type=int,
                        help=f'From URL, {NAVER_SHOPPING_CATALOG_URL}/<CATALOG_ID>')
    parser.add_argument('-p', '--chromedriver-path', type=str)
    parser.add_argument('-s', '--sort-with', type=str, choices=['ranking', 'recent'],
                        default='recent')
    parser.add_argument('-c', '--cpu-count', type=int, default=1)
    parser.add_argument('-m', '--max-page', type=int)
    parser.add_argument('-o', '--out-path', type=str,
                        help='The default path is "out/<PRODUCT_NAME>.xlsx"')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    product_name, num_review = get_info()
    if not args.max_page:
        args.max_page = min((num_review // 20) + 1, 100)
    df = run_all(args, np.arange(1, args.max_page + 1))
    filepath  = args.out_path if args.out_path else f'out/{product_name}.xlsx'
    df.to_excel(filepath)
