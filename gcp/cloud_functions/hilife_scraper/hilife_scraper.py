from selenium import webdriver
from selenium.webdriver.common.by import By
import selenium.webdriver.support.ui as ui

from selenium.webdriver.support.ui import Select
import selenium.webdriver.support.expected_conditions as EC
from tempfile import mkdtemp

from bs4 import BeautifulSoup
import traceback
import time
import datetime
import re
import sys
import logging

from google.cloud import bigquery
import os

# Configure logging at the beginning of your script
logging.basicConfig(
    level=logging.INFO,  # Set the minimum level of messages to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class crawler_cnvnts_hilife():
    def __init__(self):
        logging.info("Initializing crawler...")
        options = webdriver.ChromeOptions()
        # Add a User-Agent to mimic a regular browser
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")
        # options.binary_location = '/opt/chrome/chrome' # Commented out for Windows
        options.add_argument('--headless')
        # options.add_argument('--no-sandbox') # Commented out for Windows
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280x1696")
        # options.add_argument("--single-process") # Commented out for Windows
        # options.add_argument("--disable-dev-shm-usage") # Commented out for Windows
        # options.add_argument("--disable-dev-tools") # Keep this one
        # options.add_argument("--no-zygote") # Commented out for Windows
        # options.add_argument(f"--user-data-dir={mkdtemp()}") # Commented out for Windows
        # options.add_argument(f"--data-path={mkdtemp()}") # Commented out for Windows
        # options.add_argument(f"--disk-cache-dir={mkdtemp()}") # Commented out for Windows
        options.add_argument("--remote-debugging-port=9222")
        # old setting
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('headless')

        # Old Setting
        # option = webdriver.ChromeOptions()
        # option.add_argument('--ignore-certificate-errors')
        # option.add_argument('--ignore-ssl-errors')
        # option.add_argument('headless')

        # Update the path to your ChromeDriver executable here
        self.driver = webdriver.Chrome(options=options)

        self.store_info_result = []
        self.runned_list = []
        self.runned_city = []

        self.bigquery_client = bigquery.Client()
        self.table_id = os.environ.get("BIGQUERY_TABLE_ID", "your-gcp-project.c_store_bronze.hilife") # Default if not set in environment


    def city_extracter(self, address):
        delimiter_check = ['縣', '市']

        if any(x in address[:3] for x in delimiter_check):
            city = address[:3]
        else:
            city = '--'
        return city

    def district_extracter(self, address):
        # check if x is in district[:3], where x is from delimiter_check
        delimiter_check = ['縣', '市']
        if any(x in address[:3] for x in delimiter_check):
            district = address[3:]
            # print(district)
            district = re.split('(鄉|鎮|市|區)', district)
            if len(district) > 1:
                district = district[0] + district[1]
            else:
                district = "--"

            return district

    def timePractice(self):
        time.sleep(3)

    def gotohilife(self):
        logging.info("Starting gotohilife function...")
        self.driver.get('http://www.hilife.com.tw/storeInquiry_street.aspx')
        
        # test start
        # select = Select(self.driver.find_element(By.XPATH , '//select[@id="AREA"]'))
        #
        # select.select_by_index(0)
        # html = self.driver.page_source
        # soup = BeautifulSoup(html,'lxml')
        # city = [c.text for c in soup.find('select',{'name':'CITY'}).find_all('option')]
        # return ' '.join(city)
        # test end

        retry_count = 1
        extract_date = datetime.datetime.now().strftime("%Y/%m/%d")
        extract_time = datetime.datetime.now().strftime("%H:%M:%S")
        company = 'hilife'
        while retry_count < 10:
            try:
                logging.info(f"Attempting to select area (retry {retry_count})...")
                # Add a wait for the element to be present
                ui.WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, '//select[@id="AREA"]')))
                select = Select(self.driver.find_element(By.XPATH , '//*[@id="AREA"]'))

                select.select_by_index(0)
                html = self.driver.page_source
                soup = BeautifulSoup(html,'lxml')
                city = [c.text for c in soup.find('select',{'name':'CITY'}).find_all('option')]

                for i in range(len(city)):
                    if "{}".format(city[i]) not in self.runned_city:
                        logging.info(f"Processing city: {city[i]}")
                        try:
                            ui.WebDriverWait(self.driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR,'div.searchResults')))
                            select = Select(self.driver.find_element(By.XPATH , '//*[@id="CITY"]'))
                            select.select_by_index(i)
                            #print(city[i], '\n')
                            html_sub = self.driver.page_source
                            soup_sub = BeautifulSoup(html_sub,'lxml')
                            district = [d.text for d in soup_sub.find('select',{'name':'AREA'}).find_all('option')]
                            #time.sleep(1)
                            for j in range(len(district)):
                                if "{}{}".format(city[i], district[j]) not in self.runned_list:
                                    logging.info(f"Processing district: {city[i]} - {district[j]}")
                                    try:
                                        time.sleep(0.25)
                                        sys.stdout.write('\r{} {}'.format(city[i],district[j]))
                                        ui.WebDriverWait(self.driver,10).until(EC.presence_of_element_located((By.CSS_SELECTOR,'div.searchResults')))
                                        select = Select(self.driver.find_element(By.XPATH , '//select[@id="AREA"]'))
                                        select.select_by_index(j)
                                        html_dis = self.driver.page_source
                                        soup_dis = BeautifulSoup(html_dis,'lxml')
                                        #store_html = soup_dis.select('table[width=100%] tr')
                                        store_html = soup_dis.find('table', {'width':'100%'}).find_all('tr') #2020/03/21
                                        #print(store_html[0])

                                        for store in store_html:
                                            try:
                                                single_store = []
                                                store_name = store.select('th')[1].text

                                                address = store.select_one('a').text
                                                address = address.strip()
                                                pattern = "^[0-9][0-9][0-9]"
                                                address = re.sub(pattern,"",address).strip()
                                                ##
                                                city_data = city[i]
                                                district_data = district[j]

                                                #service = ','.join([x['title'] for x in store.select('td img[width=25]')])
                                                service = ','.join([x['title'] for x in store.find_all('img',{'width':'25'})]) #2020/03/21
                                                single_store.extend((extract_date,
                                                                    extract_time,
                                                                    company,
                                                                    store_name,
                                                                    city_data,
                                                                    district_data,
                                                                    address,
                                                                    service))
                                                self.store_info_result.append(single_store)
                                            except Exception as e:
                                                logging.warning(f"Error extracting data for a store in {city[i]} - {district[j]}: {e}")

                                        self.runned_list.append("{}{}".format(city[i], district[j]))    
                                    except Exception as e:
                                        logging.error(f"Error finding store table in {city[i]} - {district[j]}: {e}")
                            self.runned_city.append(city[i])
                        except Exception as e:
                            logging.error(f"Error waiting for search results in {city[i]}: {e}")
                    #print(self.city,'\n',self.district)
                break
            except Exception as e:
                #traceback.print_exc()
                logging.error(f"An error occurred during scraping (retry {retry_count}): {e}", exc_info=True)
                print('\nretry {}'.format(retry_count))
                retry_count +=1
        #         #time.sleep(2)

    def upload_to_bigquery(self):
        if not self.store_info_result:
            logging.info("No data to upload to BigQuery.")
            return

        # Define the schema of your BigQuery table. Ensure this matches your hilife.yaml.
        # Assuming the order: extract_date, extract_time, company, store_name, city, district, address, service
        rows_to_insert = []
        for row_data in self.store_info_result:
            # Convert list to dictionary for BigQuery insert_rows_json
            row_dict = {
                "extract_date": row_data[0],
                "extract_time": row_data[1],
                "company": row_data[2],
                "store_name": row_data[3],
                "city": row_data[4],
                "district": row_data[5],
                "address": row_data[6],
                "service": row_data[7]
            }
            rows_to_insert.append(row_dict)

        try:
            logging.info(f"Uploading {len(rows_to_insert)} rows to BigQuery table: {self.table_id}")
            errors = self.bigquery_client.insert_rows_json(self.table_id, rows_to_insert)
            if errors:
                for error in errors:
                    logging.error(f"BigQuery row insertion error: {error}")
            else:
                logging.info("New rows have been added to BigQuery.")
        except Exception as e:
            logging.error(f"An error occurred during BigQuery insertion: {e}", exc_info=True)


    def teardown(self):
        self.driver.close()


# if __name__ == "__main__":
#     scraper = crawler_cnvnts_hilife()
#     try:
#         scraper.gotohilife()
#         for store in scraper.store_info_result:
#             print(store)
#     except Exception as e:
#         logging.error("Scraper encountered an error:", exc_info=True)
#     finally:
#         scraper.teardown()
