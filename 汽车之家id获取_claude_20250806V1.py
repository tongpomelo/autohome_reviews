#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
汽车之家销量排名和车型ID爬虫
支持爬取汽车销量排名前500的数据，包括车型ID、销量、排名等信息
"""

import time
import json
import re
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autohome_sales_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class AutohomeSalesScraper:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.setup_driver()

    def setup_driver(self):
        """配置Chrome浏览器"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # 无头模式
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.7258.67 Safari/537.36')

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
            logging.info("浏览器初始化成功")
        except Exception as e:
            logging.error(f"浏览器初始化失败: {e}")
            raise

    def extract_sales_data_from_page(self):
        """从当前页面提取销量数据"""
        sales_data = []

        try:
            # 等待页面数据加载完成
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-rank-num]")))
            time.sleep(3)  # 额外等待确保数据完全加载

            # 查找所有包含排名的车型元素
            car_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-rank-num]")
            logging.info(f"找到 {len(car_elements)} 个车型元素")

            for car_element in car_elements:
                car_info = {}

                try:
                    # 提取销量排名
                    rank_num = car_element.get_attribute("data-rank-num")
                    if rank_num:
                        car_info['销量排名'] = int(rank_num)
                    else:
                        continue  # 如果没有排名，跳过这个元素

                    # 提取车型名称
                    try:
                        name_selectors = [
                            ".tw-text-nowrap.tw-text-lg.tw-font-medium",
                            ".tw-text-lg.tw-font-medium",
                            "[class*='tw-text-lg'][class*='tw-font-medium']"
                        ]

                        car_name = ""
                        for selector in name_selectors:
                            try:
                                name_elem = car_element.find_element(By.CSS_SELECTOR, selector)
                                car_name = name_elem.text.strip()
                                if car_name:
                                    break
                            except:
                                continue

                        car_info['车型名称'] = car_name

                    except Exception as e:
                        logging.warning(f"提取车型名称失败: {e}")
                        car_info['车型名称'] = ""

                    # 提取车型月销量
                    try:
                        sales_selectors = [
                            ".tw-relative.tw-top-\\[1px\\].tw-ml-\\[3px\\].tw-text-\\[18px\\].tw-font-bold",
                            "[class*='tw-text-'][class*='tw-font-bold']",
                            ".tw-font-bold"
                        ]

                        monthly_sales = ""
                        for selector in sales_selectors:
                            try:
                                sales_elems = car_element.find_elements(By.CSS_SELECTOR, selector)
                                for elem in sales_elems:
                                    text = elem.text.strip()
                                    # 检查是否是数字（销量）
                                    if text.isdigit() and len(text) >= 2:
                                        monthly_sales = text
                                        break
                                if monthly_sales:
                                    break
                            except:
                                continue

                        car_info['车型月销量'] = int(monthly_sales) if monthly_sales else 0

                    except Exception as e:
                        logging.warning(f"提取车型月销量失败: {e}")
                        car_info['车型月销量'] = 0

                    # 提取车型ID
                    try:
                        # 查找包含data-series-id的按钮或元素
                        id_selectors = [
                            "[data-series-id]",
                            "button[data-series-id]"
                        ]

                        series_id = ""
                        for selector in id_selectors:
                            try:
                                id_elem = car_element.find_element(By.CSS_SELECTOR, selector)
                                series_id = id_elem.get_attribute("data-series-id")
                                if series_id:
                                    break
                            except:
                                continue

                        car_info['车型ID'] = series_id if series_id else ""

                    except Exception as e:
                        logging.warning(f"提取车型ID失败: {e}")
                        car_info['车型ID'] = ""

                    # 提取价格区间（可选）
                    try:
                        price_selectors = [
                            ".tw-font-medium.tw-text-\\[\\#717887\\]",
                            "[class*='tw-text-'][class*='717887']"
                        ]

                        price_range = ""
                        for selector in price_selectors:
                            try:
                                price_elem = car_element.find_element(By.CSS_SELECTOR, selector)
                                price_text = price_elem.text.strip()
                                if "万" in price_text:
                                    price_range = price_text
                                    break
                            except:
                                continue

                        car_info['价格区间'] = price_range

                    except Exception as e:
                        car_info['价格区间'] = ""

                    # 提取评分（可选）
                    try:
                        score_selectors = [
                            ".tw-font-bold",
                            "strong.tw-font-bold"
                        ]

                        score = ""
                        for selector in score_selectors:
                            try:
                                score_elems = car_element.find_elements(By.CSS_SELECTOR, selector)
                                for elem in score_elems:
                                    text = elem.text.strip()
                                    # 检查是否是评分格式（如4.50）
                                    if re.match(r'^\d+\.\d+$', text):
                                        score = text
                                        break
                                if score:
                                    break
                            except:
                                continue

                        car_info['用户评分'] = float(score) if score else 0.0

                    except Exception as e:
                        car_info['用户评分'] = 0.0

                    # 添加爬取时间
                    car_info['爬取时间'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 只有当车型名称不为空时才添加到结果中
                    if car_info.get('车型名称'):
                        sales_data.append(car_info)
                        logging.info(
                            f"提取成功: 排名{car_info['销量排名']} - {car_info['车型名称']} - 销量{car_info['车型月销量']} - ID{car_info['车型ID']}")

                except Exception as e:
                    logging.error(f"提取单个车型数据失败: {e}")
                    continue

            return sales_data

        except Exception as e:
            logging.error(f"提取页面销量数据失败: {e}")
            return []

    def load_more_data(self, target_count=500):
        """加载更多数据直到达到目标数量"""
        all_data = []
        page_count = 1
        no_new_data_count = 0
        max_no_new_data = 3  # 连续3次没有新数据就停止

        try:
            # 初始页面加载
            current_data = self.extract_sales_data_from_page()
            all_data.extend(current_data)
            logging.info(f"第{page_count}页加载完成，当前总数据量: {len(all_data)}")

            while len(all_data) < target_count and no_new_data_count < max_no_new_data:
                try:
                    # 滚动到页面底部触发加载更多
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)

                    # 查找并点击"加载更多"按钮（如果存在）
                    load_more_selectors = [
                        "//button[contains(text(), '加载更多')]",
                        "//a[contains(text(), '加载更多')]",
                        "//div[contains(text(), '加载更多')]",
                        "[class*='load-more']",
                        "[class*='more-btn']"
                    ]

                    load_more_clicked = False
                    for selector in load_more_selectors:
                        try:
                            if selector.startswith("//"):
                                load_more_btn = self.driver.find_element(By.XPATH, selector)
                            else:
                                load_more_btn = self.driver.find_element(By.CSS_SELECTOR, selector)

                            if load_more_btn.is_enabled() and load_more_btn.is_displayed():
                                self.driver.execute_script("arguments[0].click();", load_more_btn)
                                load_more_clicked = True
                                logging.info("点击加载更多按钮")
                                time.sleep(5)  # 等待新数据加载
                                break
                        except:
                            continue

                    # 如果没有找到加载更多按钮，尝试滚动加载
                    if not load_more_clicked:
                        # 连续滚动几次
                        for i in range(3):
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(2)

                    # 提取新的数据
                    page_count += 1
                    current_data = self.extract_sales_data_from_page()

                    # 去重：只添加新的数据
                    existing_ranks = {item['销量排名'] for item in all_data if '销量排名' in item}
                    new_data = [item for item in current_data if item.get('销量排名') not in existing_ranks]

                    if new_data:
                        all_data.extend(new_data)
                        no_new_data_count = 0  # 重置计数器
                        logging.info(
                            f"第{page_count}页加载完成，新增{len(new_data)}条数据，当前总数据量: {len(all_data)}")
                    else:
                        no_new_data_count += 1
                        logging.info(f"第{page_count}页没有新数据，连续无新数据次数: {no_new_data_count}")

                    # 额外的等待时间，避免请求过快
                    time.sleep(3)

                except Exception as e:
                    logging.error(f"加载第{page_count}页数据时出错: {e}")
                    no_new_data_count += 1

            logging.info(f"数据加载完成，总共获取 {len(all_data)} 条数据")
            return all_data

        except Exception as e:
            logging.error(f"加载数据过程中发生错误: {e}")
            return all_data

    def scrape_sales_ranking(self, target_count=500):
        """爬取汽车销量排名数据"""
        base_url = "https://www.autohome.com.cn/rank/"

        try:
            logging.info("开始访问汽车销量排名页面")
            self.driver.get(base_url)
            time.sleep(5)

            # 等待页面完全加载
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-rank-num]")))
                logging.info("页面加载成功")
            except TimeoutException:
                logging.error("页面加载超时")
                return []

            # 加载数据
            all_data = self.load_more_data(target_count)

            # 按排名排序
            all_data.sort(key=lambda x: x.get('销量排名', 999999))

            return all_data[:target_count]  # 确保不超过目标数量

        except Exception as e:
            logging.error(f"爬取销量排名失败: {e}")
            return []

    def save_to_csv(self, data, filename):
        """保存数据到CSV文件"""
        if not data:
            logging.warning("没有数据可保存")
            return

        try:
            fieldnames = [
                '销量排名', '车型名称', '车型月销量', '车型ID',
                '价格区间', '用户评分', '爬取时间'
            ]

            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)

            logging.info(f"数据已保存到 {filename}")

        except Exception as e:
            logging.error(f"保存CSV文件失败: {e}")

    def run(self, target_count=500):
        """运行爬虫"""
        try:
            logging.info(f"开始执行汽车销量排名爬取任务，目标数据量: {target_count}")

            # 爬取销量数据
            sales_data = self.scrape_sales_ranking(target_count)

            if sales_data:
                # 保存数据
                filename = f"autohome_sales_ranking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                self.save_to_csv(sales_data, filename)

                # 打印统计信息
                logging.info(f"爬取完成！")
                logging.info(f"总数据量: {len(sales_data)}")
                logging.info(
                    f"排名范围: {min(item['销量排名'] for item in sales_data if '销量排名' in item)} - {max(item['销量排名'] for item in sales_data if '销量排名' in item)}")
                logging.info(f"有车型ID的数据: {len([item for item in sales_data if item.get('车型ID')])}")

                return sales_data
            else:
                logging.error("未获取到任何数据")
                return []

        except Exception as e:
            logging.error(f"爬虫运行失败: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()


def main():
    """主函数"""
    target_count = 500  # 目标爬取数据量

    scraper = AutohomeSalesScraper()

    try:
        logging.info("=" * 50)
        logging.info("汽车之家销量排名爬虫启动")
        logging.info("=" * 50)

        results = scraper.run(target_count)

        if results:
            logging.info("=" * 50)
            logging.info(f"任务完成！共爬取 {len(results)} 条销量数据")
            logging.info("=" * 50)

            # 显示前10名数据作为示例
            logging.info("前10名数据预览:")
            for i, item in enumerate(results[:10], 1):
                logging.info(
                    f"{i:2d}. {item.get('车型名称', 'N/A'):15} | 销量: {item.get('车型月销量', 'N/A'):>6} | ID: {item.get('车型ID', 'N/A')}")
        else:
            logging.error("爬取失败，未获取到数据")

    except KeyboardInterrupt:
        logging.info("用户中断程序")
    except Exception as e:
        logging.error(f"程序执行出错: {e}")
    finally:
        logging.info("程序结束")


if __name__ == "__main__":
    main()