import re
import traceback
from time import sleep
from multiprocessing import Pool, RawValue
from typing import Any, Dict, List, Tuple
from argparse import Action, ArgumentError, ArgumentParser, Namespace

import tqdm
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.expected_conditions import element_to_be_clickable
from selenium.webdriver.common.keys import Keys


class BlockedException(Exception):
    ...


URL_PATTERNS = {
    'shopping': re.compile(r'^https://search.shopping.naver.com/catalog/[0-9]+(:?$|\?)'),
    'brand': re.compile(r'^https://brand.naver.com/pupping/products/[0-9]+(:?$|\?)'),
}
XPATH_PRODUCT_NAME_DICT = {
    'shopping': '/html/body/div/div/div[2]/div[2]/div[1]/h2',
    'brand': '//*[@id="content"]/div/div[2]/div[2]/fieldset/div[1]/div[1]/h3',
}
XPATH_TABS_DICT = {
    'shopping': '/html/body/div/div/div[2]/div[2]/div[2]/div[3]/div[1]/ul/li',
    'brand': '//*[@id="content"]/div/div[3]/div[3]/ul/li',
}
TEXT_REVIEW_TAB_DICT = {
    'shopping': '쇼핑몰리뷰',
    'brand': '리뷰',
}
XPATH_NUM_REVIEW_DICT = {
    'shopping': './a/em',
    'brand': './a/span'
}
ID_REVIEW_SECTION_DICT = {
    'shopping': 'section_review',
    'brand': 'REVIEW',
}
XPATH_SORT_BUTTON_RECENT_DICT = { # Relative to review section
    'shopping': './div[2]/div[1]/div[1]/a[2]',
    'brand': './div/div[3]/div[1]/div[1]/ul/li[2]/a'
}
XPATH_FORMAT_PAGINATION_BUTTON = {
    'shopping': '//*[@id="section_review"]/div[3]/a[{index}]',
    'brand': '//*[@id="REVIEW"]/div/div[3]/div[2]/div/div/a[{index}]',
}
XPATH_REVIEW_ITEMS_DICT = { # Relative to review section
    'shopping': './ul/li',
    'brand': './div/div[3]/div[2]/ul/li',
}
XPATH_REVIEW_STAR_DICT = { # Relative to review item
    'shopping': './div[1]/span[1]',
    'brand': './div/div/div/div[1]/div/div[1]/div[1]/div[2]/div[1]/em'
}
XPATH_REVIEW_DATE_DICT = { # Relative to review item
    'shopping': './div[1]/span[4]',
    'brand': './div/div/div/div[1]/div/div[1]/div[1]/div[2]/div[2]/span',
}
XPATH_REVIEW_TEXT_DICT = { # Relative to review item
    'shopping': './div[2]/div[1]',
    'brand': './div/div/div/div[1]/div/div[1]/div[2]/div/span',
}
BLOCKED_URL = {
    'shopping': 'https://search.shopping.naver.com/blocked.html',
    'brand': None,
}


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
        load_webpage(chromedriver, args)
        sleep(2)
        if args.sort_with == 'recent':
            review_section = chromedriver.find_element_by_id(ID_REVIEW_SECTION_DICT[args.subdomain])
            sort_button = review_section.find_element_by_xpath(
                XPATH_SORT_BUTTON_RECENT_DICT[args.subdomain])
            sort_button.send_keys(Keys.ENTER)
            sleep(1)
        goto_page(chromedriver, args)
        review_items = crawl_review_items(chromedriver, args)
        chromedriver.quit()
        return review_items
    except Exception as e:
        if not args.debug:
            chromedriver.quit()
        raise e


def goto_page(chromedriver: webdriver.Chrome, args: Namespace) -> None:
    if args.page_number < 11:
        click_pagination_button(chromedriver, args, args.page_number)
    else:
        for i in range((args.page_number - 1) // 10):
            if i == 0:
                click_pagination_button(chromedriver, args, 11)
            else:
                click_pagination_button(chromedriver, args, 12)
        if (args.page_number - 1) % 10 > 1:
            click_pagination_button(chromedriver, args, args.page_number % 10 + 1)


def click_pagination_button(chromedriver: webdriver.Chrome, args: Namespace, index: int) -> None:
    wait = WebDriverWait(chromedriver, 10)
    xpath = XPATH_FORMAT_PAGINATION_BUTTON[args.subdomain].format(index=index)
    button = wait.until(element_to_be_clickable((By.XPATH, xpath)))
    button.click()


def crawl_review_items(chromedriver: webdriver.Chrome, args: Namespace) -> List[Dict[str, Any]]:
    items = []
    sleep(2)
    review_section = chromedriver.find_element_by_id(ID_REVIEW_SECTION_DICT[args.subdomain])
    review_items = review_section.find_elements_by_xpath(XPATH_REVIEW_ITEMS_DICT[args.subdomain])
    assert len(review_items) == 20
    for item in review_items:
        star = int(item.find_element_by_xpath(XPATH_REVIEW_STAR_DICT[args.subdomain]).text.replace('평점', ''))
        date = item.find_element_by_xpath(XPATH_REVIEW_DATE_DICT[args.subdomain]).text
        review = item.find_element_by_xpath(XPATH_REVIEW_TEXT_DICT[args.subdomain]).text
        items.append({'star': star, 'date': date, 'text': review})
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
    load_webpage(chromedriver, args)
    product_name = chromedriver.find_element_by_xpath(XPATH_PRODUCT_NAME_DICT[args.subdomain]).text
    tabs = chromedriver.find_elements_by_xpath(XPATH_TABS_DICT[args.subdomain])
    for tab in tabs:
        if TEXT_REVIEW_TAB_DICT[args.subdomain] in tab.text:
            num_review_element = tab.find_element_by_xpath(XPATH_NUM_REVIEW_DICT[args.subdomain])
            num_review = int(num_review_element.text.replace(',', ''))
            chromedriver.quit()
            break
    else:
        raise Exception('Cannot find 쇼핑몰리뷰 tab.')
        if not args.debug:
            chromedriver.quit()
    return product_name, num_review


def load_webpage(chromedriver: webdriver.Chrome, args: Namespace):
    chromedriver.get(args.url)
    if chromedriver.current_url == BLOCKED_URL[args.subdomain]:
        raise BlockedException()


def open_chromedriver(args: Namespace) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if not args.debug:
        options.add_argument('--headless')
    if args.chromedriver_path:
        chromedriver = webdriver.Chrome(args.chromedriver_path, options=options)
    else:
        chromedriver = webdriver.Chrome(options=options)
    chromedriver.minimize_window()
    chromedriver.implicitly_wait(chromedriver_wait_time.value)
    return chromedriver


class URLAction(Action):
    def __call__(self, parser: ArgumentParser, namespace: Namespace, url: str,
                 option_string: None) -> None:
        for subdomain, pattern in URL_PATTERNS.items():
            match = pattern.match(url)
            if match:
                setattr(namespace, 'url', url)
                setattr(namespace, 'subdomain', subdomain)
                break
        else:
            msg = f'Does not match to any pattern: {list(map(str, URL_PATTERNS.values()))}'
            raise ArgumentError(self, msg)


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument('url', type=str, action=URLAction) # Detect subdomain
    parser.add_argument('-p', '--chromedriver-path', type=str)
    parser.add_argument('-s', '--sort-with', type=str, choices=['ranking', 'recent'],
                        default='recent')
    parser.add_argument('-c', '--cpu-count', type=int, default=1)
    parser.add_argument('-m', '--max-page', type=int)
    parser.add_argument('-o', '--out-path', type=str,
                        help='The default path is "out/<PRODUCT_NAME>.xlsx"')
    parser.add_argument('-d', '--debug', action='store_true')
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
