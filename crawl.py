import traceback
from time import sleep
from multiprocessing import Pool, RawValue
from typing import Any, Dict, List, Tuple
from argparse import ArgumentParser, Namespace

import tqdm
import pandas as pd
from selenium import webdriver


class BlockedException(Exception):
    ...


NAVER_SHOPPING_CATALOG_URL = 'https://search.shopping.naver.com/catalog'
XPATH_PRODUCT_NAME = '/html/body/div/div/div[2]/div[2]/div[1]/h2'
XPATH_TABLIST = '/html/body/div/div/div[2]/div[2]/div[2]/div[3]/div[1]/ul'
ID_REVIEW_SECTION = 'section_review'
XPATH_SORT_BUTTON_RECENT = f'./div[2]/div[1]/div[1]/a[2]' # Relative to id=review_section
XPATH_PAGINATION = f'./div[3]'                            # Relative to id=review_section
XPATH_REVIEW_ITEMS = f'./ul/li'                           # Relative to id=review_section


chromedriver_wait_time = RawValue('i', 4)


def run(args: Namespace) -> List[Dict[str, Any]]:
    while True:
        try:
            return _run(args)
        except (KeyboardInterrupt, BlockedException):
            traceback.print_exc()
            return []
        except:
            traceback.print_exc()
            print(f'Exception from page index {args.page_number}.')
            chromedriver_wait_time.value += 1
            print(f'chromedriver wait_time is increased to {chromedriver_wait_time.value}.')


def _run(args: Namespace) -> List[Dict[str, Any]]:
    chromedriver = open_chromedriver(args)
    try:
        load_webpage(chromedriver)
        sleep(2)
        if args.sort_with == 'recent':
            review_section = chromedriver.find_element_by_id(ID_REVIEW_SECTION)
            review_section.find_element_by_xpath(XPATH_SORT_BUTTON_RECENT).click()
            sleep(1)
        goto_page(chromedriver, args.page_number)
        return crawl_review_items(chromedriver)
    finally:
        chromedriver.quit()


def goto_page(chromedriver: webdriver.Chrome, page_number: int) -> None:
    review_section = chromedriver.find_element_by_id(ID_REVIEW_SECTION)
    pagination = review_section.find_element_by_xpath(XPATH_PAGINATION)
    if page_number < 11:
        pagination.find_element_by_xpath(f'./a[{page_number}]').click()
    else:
        for i in range((page_number - 1) // 10):
            if i == 0:
                pagination.find_element_by_xpath(f'./a[11]').click()
            else:
                pagination.find_element_by_xpath(f'./a[12]').click()
            sleep(1)
        if (page_number - 1) % 10 > 1:
            pagination.find_element_by_xpath(f'./a[{page_number % 10 + 1}]').click()


def crawl_review_items(chromedriver: webdriver.Chrome) -> List[Dict[str, Any]]:
    items = []
    sleep(2)
    review_section = chromedriver.find_element_by_id(ID_REVIEW_SECTION)
    review_items = review_section.find_elements_by_xpath(XPATH_REVIEW_ITEMS)
    assert len(review_items) == 20
    for item in review_items:
        star = int(item.find_element_by_xpath('./div[1]/span[1]').text.replace('평점', ''))
        date = item.find_element_by_xpath(f'./div[1]/span[4]').text
        review = item.find_element_by_xpath('./div[2]/div[1]').text
        items.append({'star': star, 'date': date, 'review': review})
    return items


def run_all(args: Namespace, page_numbers: List[int]) -> pd.DataFrame:
    args_list = []
    for page_number in page_numbers:
        args_page = Namespace(**vars(args))
        args_page.page_number = page_number
        args_list.append(args_page)
    with Pool(args.cpu_count) as pool:
        reviews_2d = tqdm.tqdm(pool.imap(run, args_list), total=len(page_numbers))
        review_list = [r for reviews_1d in reviews_2d for r in reviews_1d]
    return pd.DataFrame(review_list)


def get_info(args: Namespace) -> Tuple[str, int]:
    chromedriver = open_chromedriver(args)
    load_webpage(chromedriver)
    print(chromedriver.current_url)
    product_name = chromedriver.find_element_by_xpath(XPATH_PRODUCT_NAME).text
    tablist = chromedriver.find_element_by_xpath(XPATH_TABLIST)
    for tab in tablist.find_elements_by_xpath('./li'):
        if '쇼핑몰리뷰' in tab.text:
            num_review = int(tab.find_element_by_xpath('./a/em').text.replace(',', ''))
            break
    else:
        raise Exception('Cannot find 쇼핑몰리뷰 tab.')
    chromedriver.quit()
    return product_name, num_review


def load_webpage(chromedriver: webdriver.Chrome):
    chromedriver.get(f'{NAVER_SHOPPING_CATALOG_URL}/{args.catalog_id}')
    if chromedriver.current_url == 'https://search.shopping.naver.com/blocked.html':
        raise BlockedException()


def open_chromedriver(args: Namespace) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if not args.show_chrome_window:
        options.add_argument('--headless')
    if args.chromedriver_path:
        chromedriver = webdriver.Chrome(args.chromedriver_path, options=options)
    else:
        chromedriver = webdriver.Chrome(options=options)
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
    parser.add_argument('-w', '--show-chrome-window', action='store_true')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    product_name, num_review = get_info(args)
    if not args.max_page:
        args.max_page = min((num_review // 20) + 1, 100)
    df = run_all(args, list(range(1, args.max_page + 1)))
    filepath  = args.out_path if args.out_path else f'out/{product_name}.xlsx'
    df.to_excel(filepath, index=False)
