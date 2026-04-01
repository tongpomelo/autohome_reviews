#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
汽车之家销量排名爬虫 - 适配26年1月新版页面
支持爬取汽车销量排名前500的数据
"""

import time
import json
import re
import csv
import os
import sys
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

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
    def __init__(self, headless=True):
        self.driver = None
        self.wait = None
        self.headless = headless
        self.setup_driver()
        self.extracted_ranks = set()  # 存储已经提取过的排名

    def setup_driver(self):
        """配置Chrome浏览器"""
        chrome_options = Options()

        # 根据参数决定是否使用无头模式
        if self.headless:
            chrome_options.add_argument('--headless=new')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        # 更真实的用户代理
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # 自动获取匹配的 ChromeDriver 路径
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)



    def extract_new_data_from_page(self):
        """从当前页面提取新增的销量数据 - 适配26年1月新版页面"""
        new_data = []

        try:
            # 等待页面数据加载完成
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-rank-num]")))
            time.sleep(1)  # 简短等待确保数据稳定

            # 查找所有包含排名的车型元素
            car_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-rank-num]")

            if not car_elements:
                # 尝试其他可能的选择器
                car_elements = self.driver.find_elements(By.CSS_SELECTOR, ".rank-list-item, .rank-item")

            logging.info(f"当前页面有 {len(car_elements)} 个车型元素")

            # 只处理新的元素（排名不在已提取集合中的）
            new_count = 0
            for car_element in car_elements:
                try:
                    # 首先获取排名
                    rank_num = car_element.get_attribute("data-rank-num")
                    if not rank_num or not rank_num.isdigit():
                        continue

                    rank = int(rank_num)

                    # 如果这个排名已经提取过，跳过
                    if rank in self.extracted_ranks:
                        continue

                    car_info = {}
                    car_info['销量排名'] = rank

                    # 1. 提取车型名称 - 适配新版选择器
                    name_selectors = [
                        ".tw-text-nowrap.tw-text-base\\/4.tw-font-semibold",  # 新版本
                        ".tw-text-nowrap.tw-text-lg.tw-font-medium",  # 老版本
                        "div[class*='tw-text-'][class*='tw-font-']",
                        ".rank-car-name",
                        ".car-name"
                    ]

                    car_name = ""
                    for selector in name_selectors:
                        try:
                            name_elements = car_element.find_elements(By.CSS_SELECTOR, selector)
                            for elem in name_elements:
                                if elem.text.strip():
                                    car_name = elem.text.strip()
                                    break
                            if car_name:
                                break
                        except:
                            continue

                    if not car_name:
                        # 尝试从div标签中查找
                        try:
                            div_elements = car_element.find_elements(By.TAG_NAME, "div")
                            for elem in div_elements:
                                text = elem.text.strip()
                                if text and len(
                                        text) < 50 and "万" not in text and "分" not in text and not text.isdigit():
                                    # 排除价格、评分、纯数字
                                    car_name = text
                                    break
                        except:
                            pass

                    car_info['车型名称'] = car_name if car_name else f"未知车型_{rank}"

                    # 2. 提取车型月销量 - 适配新版选择器
                    sales_selectors = [
                        ".tw-text-lg\\/\\[18px\\].tw-font-medium",  # 新版本
                        ".tw-text-\\[18px\\].tw-font-bold",  # 老版本
                        "span[class*='tw-text-'][class*='tw-font-']",
                        ".sales-num",
                        ".month-sales"
                    ]

                    monthly_sales = "0"
                    for selector in sales_selectors:
                        try:
                            sales_elements = car_element.find_elements(By.CSS_SELECTOR, selector)
                            for elem in sales_elements:
                                text = elem.text.strip()
                                # 提取数字（去除逗号等）
                                nums = re.findall(r'\d+', text.replace(',', ''))
                                if nums:
                                    # 尝试获取最大的数字（通常销量是最大的）
                                    nums_int = [int(n) for n in nums]
                                    max_num = max(nums_int)
                                    if max_num >= 1:  # 销量通常大于1
                                        monthly_sales = str(max_num)
                                        break
                            if monthly_sales != "0":
                                break
                        except:
                            continue

                    # 如果还没找到，尝试查找包含"车系销量"的父元素
                    if monthly_sales == "0":
                        try:
                            # 查找包含"车系销量"文本的元素
                            sales_container = car_element.find_elements(By.XPATH,
                                                                        ".//*[contains(text(), '车系销量')]/..")
                            for container in sales_container:
                                # 在容器中查找所有数字
                                numbers = re.findall(r'\d+', container.text.replace(',', ''))
                                if numbers:
                                    nums_int = [int(n) for n in numbers]
                                    max_num = max(nums_int)
                                    if max_num > 1000:  # 销量通常大于1000
                                        monthly_sales = str(max_num)
                                        break
                        except:
                            pass

                    car_info['车型月销量'] = int(monthly_sales) if monthly_sales.isdigit() else 0

                    # 3. 提取车型ID - 新版本已移除，需要从其他途径获取
                    # 方法1：尝试从图片URL中提取（如果包含车型ID）
                    series_id = ""
                    try:
                        # 查找图片元素
                        img_elements = car_element.find_elements(By.TAG_NAME, "img")
                        for img in img_elements:
                            src = img.get_attribute("src") or ""
                            # 尝试从URL中提取可能的ID
                            # 例如：//g.autoimg.cn/@img/car2/cardfs/series/g31/...
                            match = re.search(r'/series/([a-zA-Z0-9]+)/', src)
                            if match:
                                series_id = match.group(1)
                                break
                    except:
                        pass

                    # 方法2：尝试从按钮中提取（旧版本）
                    if not series_id:
                        try:
                            buttons = car_element.find_elements(By.TAG_NAME, "button")
                            for btn in buttons:
                                sid = btn.get_attribute("data-series-id")
                                if sid and sid.isdigit():
                                    series_id = sid
                                    break
                        except:
                            pass

                    car_info['车型ID'] = series_id if series_id else "N/A"

                    # 4. 提取价格区间 - 适配新版选择器
                    price_selectors = [
                        ".tw-text-sm\\/\\[14px\\].tw-font-medium.tw-text-\\[\\#717887\\]",  # 新版本
                        ".tw-font-medium.tw-text-\\[\\#717887\\]",  # 老版本
                        ".price-range",
                        ".car-price"
                    ]

                    price_range = ""
                    for selector in price_selectors:
                        try:
                            price_elements = car_element.find_elements(By.CSS_SELECTOR, selector)
                            for elem in price_elements:
                                text = elem.text.strip()
                                if "万" in text:
                                    price_range = text
                                    break
                            if price_range:
                                break
                        except:
                            continue

                    car_info['价格区间'] = price_range

                    # 5. 提取评分 - 适配新版选择器
                    score = "0.0"
                    try:
                        # 新版评分结构
                        score_selectors_new = [
                            ".tw-font-harmony.tw-text-sm\\/\\[14px\\]",
                            "span[class*='tw-font-harmony']"
                        ]

                        for selector in score_selectors_new:
                            try:
                                score_elements = car_element.find_elements(By.CSS_SELECTOR, selector)
                                for elem in score_elements:
                                    text = elem.text.strip()
                                    if re.match(r'^\d+\.\d+$', text):
                                        score = text
                                        break
                                if score != "0.0":
                                    break
                            except:
                                continue

                        # 如果新版没找到，尝试老版
                        if score == "0.0":
                            score_selectors_old = [
                                ".tw-font-bold",
                                "strong.tw-font-bold"
                            ]

                            for selector in score_selectors_old:
                                try:
                                    score_elements = car_element.find_elements(By.CSS_SELECTOR, selector)
                                    for elem in score_elements:
                                        text = elem.text.strip()
                                        if re.match(r'^\d+\.\d+$', text):
                                            score = text
                                            break
                                    if score != "0.0":
                                        break
                                except:
                                    continue
                    except:
                        pass

                    car_info['用户评分'] = float(score) if re.match(r'^\d+\.\d+$', score) else 0.0

                    # 6. 添加时间戳
                    car_info['爬取时间'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 添加到结果列表并记录已提取的排名
                    new_data.append(car_info)
                    self.extracted_ranks.add(rank)
                    new_count += 1

                    # 每提取10条数据打印一次进度
                    if new_count % 10 == 0:
                        logging.info(f"已提取 {new_count} 条新数据...")

                except Exception as e:
                    logging.warning(f"提取排名 {rank} 的数据失败: {e}")
                    continue

            if new_data:
                logging.info(f"本次提取了 {len(new_data)} 条新数据")

            return new_data

        except Exception as e:
            logging.error(f"提取页面销量数据失败: {e}")
            return []

    def scroll_to_load_more(self, target_count=500, max_scrolls=30):
        """通过滚动加载更多数据"""
        all_data = []
        last_height = 0
        same_height_count = 0
        max_same_height = 3  # 连续3次高度不变认为加载完成

        # 首先提取初始页面的数据
        initial_data = self.extract_new_data_from_page()
        all_data.extend(initial_data)

        logging.info(f"初始页面提取 {len(initial_data)} 条数据，总计 {len(all_data)} 条")

        # 检查是否已达到目标数量
        if len(all_data) >= target_count:
            logging.info(f"初始页面已达到目标数量 {target_count}")
            return all_data[:target_count]

        for scroll in range(max_scrolls):
            # 滚动页面
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2.5)  # 等待数据加载

            # 提取新增数据
            current_data = self.extract_new_data_from_page()

            if current_data:
                all_data.extend(current_data)
                logging.info(f"滚动 {scroll + 1} 次，新增 {len(current_data)} 条，总计 {len(all_data)} 条")

            # 检查是否达到目标数量
            if len(all_data) >= target_count:
                logging.info(f"已达到目标数量 {target_count}")
                break

            # 检查页面高度是否变化
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                same_height_count += 1
                if same_height_count >= max_same_height:
                    logging.info(f"页面高度连续 {max_same_height} 次未变化，可能已加载全部数据")
                    break
            else:
                same_height_count = 0
                last_height = new_height

            # 短暂等待，避免请求过快
            time.sleep(1)

        return all_data[:target_count]

    def scrape_sales_ranking(self, target_count=500):
        """爬取汽车销量排名数据"""
        # 根据文档，URL可能是 https://www.autohome.com.cn/rank/1
        base_url = "https://www.autohome.com.cn/rank/"

        # 尝试不同的URL格式
        urls_to_try = [
            "https://www.autohome.com.cn/rank/1",
            "https://www.autohome.com.cn/rank",
            "https://www.autohome.com.cn/rank/#pvareaid=3311265"
        ]

        for url in urls_to_try:
            try:
                logging.info(f"尝试访问: {url}")
                self.driver.get(url)
                time.sleep(3)  # 等待页面加载

                # 检查是否成功加载了数据
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))

                # 检查是否有排名相关元素
                try:
                    test_elements = self.driver.find_elements(By.CSS_SELECTOR,
                                                              "[data-rank-num], .rank-list, .rank-item")
                    if test_elements:
                        logging.info(f"成功访问到排名页面: {url}")
                        break
                except:
                    continue

            except Exception as e:
                logging.warning(f"访问 {url} 失败: {e}")

        # 通过滚动加载数据
        all_data = self.scroll_to_load_more(target_count)

        # 按排名排序
        all_data.sort(key=lambda x: x.get('销量排名', 999999))

        return all_data[:target_count]

    def save_to_csv(self, data, filename=None):
        """保存数据到CSV文件"""
        if not data:
            logging.warning("没有数据可保存")
            return False

        try:
            if not filename:
                filename = f"汽车之家销量排名_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            fieldnames = ['销量排名', '车型名称', '车型月销量', '车型ID', '价格区间', '用户评分', '爬取时间']

            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)

            logging.info(f"数据已保存到 {filename}")
            return True

        except Exception as e:
            logging.error(f"保存CSV文件失败: {e}")
            return False

    def save_to_json(self, data, filename=None):
        """保存数据到JSON文件"""
        if not data:
            return False

        try:
            if not filename:
                filename = f"汽车之家销量排名_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logging.info(f"数据已保存到 {filename}")
            return True

        except Exception as e:
            logging.error(f"保存JSON文件失败: {e}")
            return False

    def run(self, target_count=500, save_format='csv'):
        """运行爬虫"""
        try:
            logging.info(f"开始执行汽车销量排名爬取任务，目标数据量: {target_count}")

            # 清空已提取记录
            self.extracted_ranks = set()

            # 爬取销量数据
            sales_data = self.scrape_sales_ranking(target_count)

            if sales_data:
                # 保存数据
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                if save_format.lower() == 'csv':
                    filename = f"汽车之家销量排名_{timestamp}.csv"
                    self.save_to_csv(sales_data, filename)
                elif save_format.lower() == 'json':
                    filename = f"汽车之家销量排名_{timestamp}.json"
                    self.save_to_json(sales_data, filename)
                else:
                    # 两种格式都保存
                    self.save_to_csv(sales_data, f"汽车之家销量排名_{timestamp}.csv")
                    self.save_to_json(sales_data, f"汽车之家销量排名_{timestamp}.json")

                # 打印统计信息
                logging.info("=" * 60)
                logging.info(f"爬取完成！")
                logging.info(f"总数据量: {len(sales_data)}")
                logging.info(
                    f"排名范围: {min(item['销量排名'] for item in sales_data)} - {max(item['销量排名'] for item in sales_data)}")
                logging.info(
                    f"成功获取车型ID的数据: {len([item for item in sales_data if item.get('车型ID') and item['车型ID'] != 'N/A'])}")
                if sales_data:
                    logging.info(f"平均月销量: {sum(item['车型月销量'] for item in sales_data) // len(sales_data):,}")
                logging.info("=" * 60)

                # 显示前10名数据
                logging.info("\n前10名数据预览:")
                logging.info(
                    "排名 | 车型名称".ljust(30) + " | 月销量".ljust(10) + " | 车型ID".ljust(15) + " | 价格区间")
                logging.info("-" * 85)
                for item in sales_data[:10]:
                    name = item['车型名称'][:25] if len(item['车型名称']) > 25 else item['车型名称'].ljust(25)
                    car_id = item['车型ID'][:15] if item['车型ID'] else "N/A"
                    logging.info(
                        f"{item['销量排名']:4d} | {name} | {item['车型月销量']:8,} | {car_id:15} | {item['价格区间']}")

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


def check_chromedriver():
    """检查ChromeDriver状态"""
    logging.info("=" * 60)
    logging.info("检查ChromeDriver状态")

    # 检查常见路径
    common_paths = [
        r'D:\1. 个人研究生论文工作\20. 数据分析整理\chromedriver-win64\chromedriver.exe',
        r'D:/1. 个人研究生论文工作/20. 数据分析整理/chromedriver-win64/chromedriver.exe',
        os.path.join(os.getcwd(), 'chromedriver.exe'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chromedriver.exe'),
        'chromedriver.exe'
    ]

    for path in common_paths:
        if os.path.exists(path):
            logging.info(f"✓ 找到ChromeDriver: {path}")
            return path
        else:
            logging.info(f"✗ 路径不存在: {path}")

    logging.info("未找到ChromeDriver，请按以下步骤操作：")
    logging.info("1. 下载ChromeDriver（与您的Chrome浏览器版本匹配）")
    logging.info("2. 下载地址：https://chromedriver.chromium.org/")
    logging.info("3. 将chromedriver.exe放在以下任一位置：")
    for path in common_paths[:-1]:  # 排除最后一个（PATH中的）
        logging.info(f"   - {path}")
    logging.info("=" * 60)
    return None


def main():
    """主函数"""
    # 首先检查ChromeDriver状态
    check_chromedriver()

    # 设置爬取参数
    target_count = 20  # 先尝试爬取20条数据（调试阶段）
    headless_mode = False  # 调试时设为False可以看到浏览器操作
    save_format = 'csv'  # 保存格式: csv 或 json

    scraper = AutohomeSalesScraper(headless=headless_mode)

    try:
        logging.info("=" * 60)
        logging.info("汽车之家销量排名爬虫启动 - 适配26年1月新版")
        logging.info(f"目标数量: {target_count}")
        logging.info(f"无头模式: {headless_mode}")
        logging.info(f"保存格式: {save_format}")
        logging.info("=" * 60)

        results = scraper.run(target_count, save_format)

        if results:
            logging.info(f"任务完成！共爬取 {len(results)} 条销量数据")
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