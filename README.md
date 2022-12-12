# NaverShoppingReviewCrawler

Naver shopping review crawler (22.12.01)


## Prerequisites
### Python environment
This project is developed and tested with python3.9.

### Install libraries
```bash
python -m pip install -r requirements.txt
```

## Getting Started

### Catalog ID
Get the catalog ID from URL,
"https://search.shopping.naver.com/catalog/<CATALOG_ID>".

### Run the crawler
```bash
python crawl.py <CATALOG_ID>
# The result is saved in "out/<PRODUCT_NAME>.xlsx"
```

## Options
```bash
python crawl.py -h
```
```
usage: crawl.py [-h] [-p CHROMEDRIVER_PATH] [-s {ranking,recent}] [-c CPU_COUNT] [-m MAX_PAGE] [-o OUT_PATH] catalog_id

positional arguments:
  catalog_id            From URL, https://search.shopping.naver.com/catalog/<CATALOG_ID>

optional arguments:
  -h, --help            show this help message and exit
  -p CHROMEDRIVER_PATH, --chromedriver-path CHROMEDRIVER_PATH
  -s {ranking,recent}, --sort-with {ranking,recent}
  -c CPU_COUNT, --cpu-count CPU_COUNT
  -m MAX_PAGE, --max-page MAX_PAGE
  -o OUT_PATH, --out-path OUT_PATH
                        The default path is "out/<PRODUCT_NAME>.xlsx"
```

Large number of CPU_COUNT may cause block from the server.
