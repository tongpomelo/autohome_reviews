#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
汽车之家口碑评论爬虫 - 增强版 V5
支持从CSV文件读取车型ID，按销量排名和车型名称生成有序分表
新增：观看数、点赞数、评论数、购车目的
"""

import time
import re
import csv
import os
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autohome_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class AutohomeReviewScraper:
    def __init__(self, output_dir="autohome_reviews_output"):
        self.driver = None
        self.wait = None
        self.output_dir = output_dir
        self.setup_output_directory()
        self.setup_driver()

    def setup_output_directory(self):
        """创建输出目录"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logging.info(f"创建输出目录: {self.output_dir}")

    def load_car_info_from_csv(self, csv_file="autohome_sales_ranking_id.csv"):
        """从CSV文件读取车型信息"""
        try:

            df = pd.read_csv(csv_file, encoding='gbk')

            # 检查必要的列是否存在
            required_columns = ['车型ID', '销量排名', '车型名称']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logging.error(f"CSV文件缺少必要列: {missing_columns}")
                return []

            # 按销量排名排序
            df = df.sort_values('销量排名')

            car_info_list = []
            for _, row in df.iterrows():
                car_info = {
                    '车型ID': str(row['车型ID']),
                    '销量排名': int(row['销量排名']),
                    '车型名称': str(row['车型名称']).strip()
                }
                car_info_list.append(car_info)

            logging.info(f"从{csv_file}读取到{len(car_info_list)}个车型信息")
            return car_info_list

        except FileNotFoundError:
            logging.error(f"找不到文件: {csv_file}")
            return []
        except Exception as e:
            logging.error(f"读取CSV文件失败: {e}")
            return []

    def setup_driver(self):
        """配置Chrome浏览器 - 使用本地ChromeDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.7258.128')

        try:
            # 指定本地 ChromeDriver 路径
            # 请将下面的路径替换为您实际的 ChromeDriver 路径
            driver_path = r'C:\Users\016053\.wdm\drivers\chromedriver\win64\139.0.7258.68\chromedriver-win32\chromedriver.exe'

            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
            logging.info("浏览器初始化成功")

            # 添加测试验证
            self.driver.get("https://www.baidu.com")
            logging.info(f"浏览器测试成功！标题: {self.driver.title}")
            return True
        except Exception as e:
            logging.error(f"浏览器初始化失败: {e}")
            # 添加详细错误信息
            import traceback
            logging.error(traceback.format_exc())
            # 尝试回退到WebDriver Manager
            logging.warning("尝试使用WebDriver Manager初始化...")
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.wait = WebDriverWait(self.driver, 10)
                logging.info("浏览器初始化成功（使用WebDriver Manager）")
                self.driver.get("https://www.baidu.com")
                logging.info(f"浏览器测试成功！标题: {self.driver.title}")
                return True
            except Exception as fallback_e:
                logging.error(f"WebDriver Manager初始化也失败: {fallback_e}")
                logging.error(traceback.format_exc())
                return False

    def extract_star_rating(self, star_element):
        """从星级元素中提取评分"""
        try:
            star_fill = star_element.find_element(By.CLASS_NAME, "kb-star")
            width_style = star_fill.get_attribute("style")
            width_match = re.search(r'width:\s*(\d+)%', width_style)
            if width_match:
                width_percent = int(width_match.group(1))
                return round(width_percent / 20, 1)  # 转换为5分制
            return 0
        except:
            return 0
    def extract_publish_time(self):
        """提取发表时间 - 新增功能"""
        try:
            # 查找时间线容器
            timeline_selectors = [
                "div.timeline-con span",
                "div.timeline-con .timeline + span",
                "span:contains('首次发表')",
                ".timeline-con span"
            ]

            for selector in timeline_selectors:
                try:
                    if 'contains' in selector:
                        # 使用XPath查找包含"首次发表"的span
                        timeline_elem = self.driver.find_element(By.XPATH, "//span[contains(text(), '首次发表')]")
                    else:
                        timeline_elem = self.driver.find_element(By.CSS_SELECTOR, selector)

                    timeline_text = timeline_elem.text.strip()
                    logging.info(f"找到时间线文本: {timeline_text}")

                    # 提取日期，支持多种格式
                    date_patterns = [
                        r'(\d{4}-\d{2}-\d{2})\s+首次发表',  # 2025-08-15 首次发表
                        r'(\d{4}-\d{1,2}-\d{1,2})\s+首次发表',  # 支持单数日期
                        r'(\d{4}/\d{2}/\d{2})\s+首次发表',  # 2025/08/15 首次发表
                        r'(\d{4}\.\d{2}\.\d{2})\s+首次发表',  # 2025.08.15 首次发表
                        r'(\d{4}-\d{2}-\d{2})',  # 仅日期格式
                    ]

                    for pattern in date_patterns:
                        match = re.search(pattern, timeline_text)
                        if match:
                            publish_date = match.group(1)
                            # 标准化日期格式为 YYYY-MM-DD
                            if '/' in publish_date:
                                publish_date = publish_date.replace('/', '-')
                            elif '.' in publish_date:
                                publish_date = publish_date.replace('.', '-')

                            logging.info(f"成功提取发表时间: {publish_date}")
                            return publish_date

                except NoSuchElementException:
                    continue
                except Exception as e:
                    logging.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            # 如果上面的方法都失败，尝试更通用的方法
            try:
                # 查找所有包含日期格式的span元素
                all_spans = self.driver.find_elements(By.TAG_NAME, "span")
                for span in all_spans:
                    text = span.text.strip()
                    if '首次发表' in text or re.match(r'\d{4}-\d{1,2}-\d{1,2}', text):
                        date_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})', text)
                        if date_match:
                            publish_date = date_match.group(1)
                            logging.info(f"通过遍历找到发表时间: {publish_date}")
                            return publish_date
            except Exception as e:
                logging.debug(f"遍历span查找时间失败: {e}")

            logging.warning("未找到发表时间")
            return ""

        except Exception as e:
            logging.error(f"提取发表时间失败: {e}")
            return ""

    def extract_car_info(self):
        """提取车辆基本信息"""
        car_info = {}
        try:
            # 车型名称
            try:
                car_name = self.driver.find_element(By.CSS_SELECTOR, ".main-series").text
                car_info['车型名称'] = car_name.strip()
            except NoSuchElementException:
                car_info['车型名称'] = ""

            # 车型版本
            try:
                car_spec = self.driver.find_element(By.CSS_SELECTOR, ".main-spec").text
                car_info['车型版本'] = car_spec.strip()
            except NoSuchElementException:
                car_info['车型版本'] = ""

            # 新增：提取发表时间（在车型版本和行驶里程之间）
            car_info['发表时间'] = self.extract_publish_time()


            # 车辆详细信息
            info_items = {
                '行驶里程': '', '夏季电耗': '', '春秋电耗': '', '冬季电耗': '',
                '夏季续航': '', '春秋续航': '', '冬季续航': '', '百公里油耗': '',
                '裸车购买价': '', '购买时间': '', '购买地点': ''
            }

            try:
                car_info_sections = self.driver.find_elements(By.CSS_SELECTOR, "ul.car-info")
                for section in car_info_sections:
                    items = section.find_elements(By.CSS_SELECTOR, "li.item-info")
                    for item in items:
                        try:
                            key_elem = item.find_element(By.CSS_SELECTOR, ".key")
                            name_elem = item.find_element(By.CSS_SELECTOR, ".name")
                            key_text = key_elem.text.strip()
                            name_text = name_elem.text.strip()

                            if name_text in info_items:
                                info_items[name_text] = key_text
                        except:
                            continue
            except:
                pass

            car_info.update(info_items)
            return car_info

        except Exception as e:
            logging.error(f"提取车辆信息失败: {e}")
            return car_info

    def extract_interaction_data(self):
        """从详情页提取观看数、点赞数、评论数 - 处理隐藏元素版本"""
        interaction_data = {
            '观看数': 0,
            '点赞数': 0,
            '评论数': 0
        }

        try:
            # 等待页面完全加载
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)

            # 关键步骤：触发隐藏元素显示
            logging.info("尝试触发隐藏的交互数据元素显示...")

            # 方法1：滚动到页面中间位置触发元素显示
            try:
                # 获取页面高度并滚动到中间位置
                page_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_to = page_height // 2

                self.driver.execute_script(f"window.scrollTo(0, {scroll_to});")
                time.sleep(1)

                # 再滚动一点确保触发
                self.driver.execute_script("window.scrollBy(0, 200);")
                time.sleep(1)

                logging.info(f"已滚动到页面中间位置 ({scroll_to}px)")

            except Exception as e:
                logging.warning(f"滚动触发失败: {e}")

            # 方法2：查找并悬停在可能触发显示的元素上
            try:
                # 查找可能的触发元素（如评论区域、内容区域等）
                trigger_selectors = [
                    ".kb-item",  # 评论项目
                    ".main-content",  # 主要内容
                    ".detail-content",  # 详情内容
                    ".space.kb-item"  # 评论空间
                ]

                for selector in trigger_selectors:
                    try:
                        trigger_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        # 滚动到元素位置
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger_element)
                        time.sleep(1)

                        # 模拟鼠标悬停
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(self.driver).move_to_element(trigger_element).perform()
                        time.sleep(1)
                        break
                    except:
                        continue

            except Exception as e:
                logging.warning(f"悬停触发失败: {e}")

            # 方法3：尝试移除fn-hide类
            try:
                # 查找带有fn-hide类的options元素
                hidden_options = self.driver.find_elements(By.CSS_SELECTOR, "div.options.fn-hide")
                for element in hidden_options:
                    # 使用JavaScript移除fn-hide类
                    self.driver.execute_script("arguments[0].classList.remove('fn-hide');", element)
                    logging.info("已移除fn-hide类，元素应该显示了")

                time.sleep(1)  # 等待元素显示

            except Exception as e:
                logging.warning(f"移除fn-hide类失败: {e}")

            # 方法4：直接使用JavaScript强制显示隐藏元素
            try:
                show_script = """
                // 查找所有隐藏的options元素并显示
                var hiddenElements = document.querySelectorAll('div.options.fn-hide');
                hiddenElements.forEach(function(element) {
                    element.classList.remove('fn-hide');
                    element.style.display = 'block';
                    element.style.visibility = 'visible';
                });

                // 同时显示所有可能隐藏的交互数据元素
                var interactionElements = document.querySelectorAll('.option-views, .option-goods, .option-comments');
                interactionElements.forEach(function(element) {
                    element.style.display = 'inline';
                    element.style.visibility = 'visible';
                });

                return hiddenElements.length;
                """

                hidden_count = self.driver.execute_script(show_script)
                if hidden_count > 0:
                    logging.info(f"通过JavaScript显示了 {hidden_count} 个隐藏的options元素")
                    time.sleep(1)  # 等待显示完成

            except Exception as e:
                logging.warning(f"JavaScript显示元素失败: {e}")

            # 现在开始提取数据 - 使用多种策略

            # 策略1：直接查找显示的元素
            try:
                # 观看数
                view_elements = self.driver.find_elements(By.CSS_SELECTOR, "span.option-views")
                for elem in view_elements:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text.isdigit():
                            interaction_data['观看数'] = int(text)
                            logging.info(f"成功提取观看数: {interaction_data['观看数']}")
                            break

                # 点赞数
                good_elements = self.driver.find_elements(By.CSS_SELECTOR, "span.option-goods")
                for elem in good_elements:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text.isdigit():
                            interaction_data['点赞数'] = int(text)
                            logging.info(f"成功提取点赞数: {interaction_data['点赞数']}")
                            break

                # 评论数
                comment_elements = self.driver.find_elements(By.CSS_SELECTOR, "span.option-comments")
                for elem in comment_elements:
                    if elem.is_displayed():
                        text = elem.text.strip()
                        if text.isdigit():
                            interaction_data['评论数'] = int(text)
                            logging.info(f"成功提取评论数: {interaction_data['评论数']}")
                            break

            except Exception as e:
                logging.error(f"策略1提取失败: {e}")

            # 策略2：如果策略1失败，直接获取所有匹配元素的内容（包括隐藏的）
            if all(value == 0 for value in interaction_data.values()):
                logging.warning("策略1失败，尝试策略2：获取所有匹配元素（包括隐藏的）")

                try:
                    # 使用JavaScript直接获取元素内容，绕过显示状态检查
                    interaction_script = """
                    var result = {views: 0, goods: 0, comments: 0};

                    // 获取观看数
                    var viewElements = document.querySelectorAll('span.option-views');
                    for (var i = 0; i < viewElements.length; i++) {
                        var text = viewElements[i].textContent.trim();
                        if (/^\d+$/.test(text)) {
                            result.views = parseInt(text);
                            break;
                        }
                    }

                    // 获取点赞数
                    var goodElements = document.querySelectorAll('span.option-goods');
                    for (var i = 0; i < goodElements.length; i++) {
                        var text = goodElements[i].textContent.trim();
                        if (/^\d+$/.test(text)) {
                            result.goods = parseInt(text);
                            break;
                        }
                    }

                    // 获取评论数
                    var commentElements = document.querySelectorAll('span.option-comments');
                    for (var i = 0; i < commentElements.length; i++) {
                        var text = commentElements[i].textContent.trim();
                        if (/^\d+$/.test(text)) {
                            result.comments = parseInt(text);
                            break;
                        }
                    }

                    return result;
                    """

                    js_result = self.driver.execute_script(interaction_script)
                    if js_result:
                        interaction_data['观看数'] = js_result.get('views', 0)
                        interaction_data['点赞数'] = js_result.get('goods', 0)
                        interaction_data['评论数'] = js_result.get('comments', 0)

                        logging.info(
                            f"通过JavaScript成功提取: 观看{interaction_data['观看数']} 点赞{interaction_data['点赞数']} 评论{interaction_data['评论数']}")

                except Exception as e:
                    logging.error(f"策略2（JavaScript）失败: {e}")

            # 策略3：如果还是失败，尝试查找options容器并强制显示
            if all(value == 0 for value in interaction_data.values()):
                logging.warning("策略2也失败，尝试策略3：查找并处理options容器")

                try:
                    # 查找所有options容器（无论是否隐藏）
                    options_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.options")

                    for container in options_containers:
                        # 强制显示容器
                        self.driver.execute_script("""
                            arguments[0].classList.remove('fn-hide');
                            arguments[0].style.display = 'block';
                            arguments[0].style.visibility = 'visible';
                        """, container)

                        # 滚动到容器位置
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", container)
                        time.sleep(1)

                        # 在这个容器中查找交互数据
                        try:
                            view_span = container.find_element(By.CSS_SELECTOR, "span.option-views")
                            if view_span.text.strip().isdigit():
                                interaction_data['观看数'] = int(view_span.text.strip())
                        except:
                            pass

                        try:
                            good_span = container.find_element(By.CSS_SELECTOR, "span.option-goods")
                            if good_span.text.strip().isdigit():
                                interaction_data['点赞数'] = int(good_span.text.strip())
                        except:
                            pass

                        try:
                            comment_span = container.find_element(By.CSS_SELECTOR, "span.option-comments")
                            if comment_span.text.strip().isdigit():
                                interaction_data['评论数'] = int(comment_span.text.strip())
                        except:
                            pass

                        # 如果在这个容器中找到了数据，就退出循环
                        if any(value > 0 for value in interaction_data.values()):
                            logging.info(f"在options容器中成功找到交互数据")
                            break

                except Exception as e:
                    logging.error(f"策略3失败: {e}")

            # 调试：输出最终状态
            if all(value == 0 for value in interaction_data.values()):
                logging.warning("所有策略都失败，进行最终调试...")

                try:
                    # 检查页面中是否存在目标元素
                    debug_script = """
                    var debug = {
                        optionsContainers: document.querySelectorAll('div.options').length,
                        hiddenOptionsContainers: document.querySelectorAll('div.options.fn-hide').length,
                        visibleOptionsContainers: document.querySelectorAll('div.options:not(.fn-hide)').length,
                        viewSpans: document.querySelectorAll('span.option-views').length,
                        goodSpans: document.querySelectorAll('span.option-goods').length,
                        commentSpans: document.querySelectorAll('span.option-comments').length,
                        allSpansWithNumbers: []
                    };

                    // 收集所有包含数字的span
                    var allSpans = document.querySelectorAll('span');
                    for (var i = 0; i < allSpans.length && debug.allSpansWithNumbers.length < 10; i++) {
                        var text = allSpans[i].textContent.trim();
                        if (/^\d+$/.test(text)) {
                            debug.allSpansWithNumbers.push({
                                text: text,
                                className: allSpans[i].className,
                                displayed: allSpans[i].offsetParent !== null
                            });
                        }
                    }

                    return debug;
                    """

                    debug_info = self.driver.execute_script(debug_script)
                    logging.info(f"调试信息: {debug_info}")

                except Exception as e:
                    logging.error(f"调试脚本失败: {e}")

            logging.info(
                f"最终交互数据: 观看{interaction_data['观看数']} 点赞{interaction_data['点赞数']} 评论{interaction_data['评论数']}")
            return interaction_data

        except Exception as e:
            logging.error(f"提取交互数据失败: {e}")
            return interaction_data

    def debug_page_structure(self):
        """调试函数：分析页面结构，找出正确的选择器"""
        try:
            logging.info("开始分析页面结构...")

            # 1. 打印页面标题确认页面已加载
            logging.info(f"当前页面标题: {self.driver.title}")

            # 2. 查找所有包含数字的span元素
            spans_with_numbers = self.driver.find_elements(By.XPATH, "//span[text()[matches(., '\\d+')]]")
            logging.info(f"找到 {len(spans_with_numbers)} 个包含数字的span元素:")

            for i, span in enumerate(spans_with_numbers[:10]):  # 只显示前10个
                try:
                    text = span.text.strip()
                    class_name = span.get_attribute('class')
                    logging.info(f"  Span {i + 1}: 文本='{text}', class='{class_name}'")
                except:
                    continue

            # 3. 查找所有可能相关的class
            all_elements = self.driver.find_elements(By.XPATH,
                                                     "//*[contains(@class, 'option') or contains(@class, 'count') or contains(@class, 'num') or contains(@class, 'data')]")
            logging.info(f"找到 {len(all_elements)} 个可能相关的元素:")

            for i, elem in enumerate(all_elements[:10]):  # 只显示前10个
                try:
                    text = elem.text.strip()
                    class_name = elem.get_attribute('class')
                    tag_name = elem.tag_name
                    logging.info(f"  元素 {i + 1}: 标签={tag_name}, 文本='{text}', class='{class_name}'")
                except:
                    continue

            # 4. 保存页面源码用于分析
            page_source = self.driver.page_source
            debug_file = os.path.join(self.output_dir,
                                      f"debug_page_source_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page_source)
            logging.info(f"页面源码已保存到: {debug_file}")

        except Exception as e:
            logging.error(f"调试页面结构失败: {e}")

    def extract_review_details(self):
        """提取详细评论信息 - 修复版"""
        review_data = {}

        try:
            # 修复：提取最满意 - 使用多种选择器尝试
            review_data['最满意'] = ""
            satisfied_selectors = [
                "//h1[contains(text(), '最满意')]/following-sibling::p[@class='kb-item-msg']",
                "//h1[text()='最满意']/following-sibling::p[@class='kb-item-msg']",
                "//div[@class='space kb-item']//h1[contains(text(), '最满意')]/following-sibling::p",
                "//div[contains(@class, 'kb-item')]//h1[contains(text(), '最满意')]/../p[@class='kb-item-msg']"
            ]

            for selector in satisfied_selectors:
                try:
                    satisfied_elem = self.driver.find_element(By.XPATH, selector)
                    review_data['最满意'] = satisfied_elem.text.strip()
                    logging.info(f"成功提取最满意内容: {review_data['最满意'][:50]}...")
                    break
                except:
                    continue

            # 修复：提取最不满意 - 使用多种选择器尝试
            review_data['最不满意'] = ""
            unsatisfied_selectors = [
                "//h1[contains(text(), '最不满意')]/following-sibling::p[@class='kb-item-msg']",
                "//h1[text()='最不满意']/following-sibling::p[@class='kb-item-msg']",
                "//div[@class='space kb-item']//h1[contains(text(), '最不满意')]/following-sibling::p",
                "//div[contains(@class, 'kb-item')]//h1[contains(text(), '最不满意')]/../p[@class='kb-item-msg']"
            ]

            for selector in unsatisfied_selectors:
                try:
                    unsatisfied_elem = self.driver.find_element(By.XPATH, selector)
                    review_data['最不满意'] = unsatisfied_elem.text.strip()
                    logging.info(f"成功提取最不满意内容: {review_data['最不满意'][:50]}...")
                    break
                except:
                    continue

            # 打印页面源码用于调试（可选）
            if not review_data['最满意'] and not review_data['最不满意']:
                logging.warning("最满意和最不满意都为空，尝试查找页面结构")
                # 查找所有包含"满意"的元素
                try:
                    all_h1 = self.driver.find_elements(By.TAG_NAME, "h1")
                    for h1 in all_h1:
                        if "满意" in h1.text:
                            logging.info(f"找到满意相关标题: {h1.text}")
                except:
                    pass

            # 提取各项评分和评论
            categories = ['空间', '驾驶感受', '续航', '外观', '内饰', '性价比', '智能化', '油耗', '配置']

            for category in categories:
                try:
                    # 使用更灵活的选择器查找分类
                    category_selectors = [
                        f"//h1[contains(text(), '{category}')]",
                        f"//div[@class='space kb-item']//h1[contains(text(), '{category}')]"
                    ]

                    category_elem = None
                    for selector in category_selectors:
                        try:
                            category_elem = self.driver.find_element(By.XPATH, selector)
                            break
                        except:
                            continue

                    if category_elem:
                        # 提取评分
                        try:
                            star_container = category_elem.find_element(By.CSS_SELECTOR, ".athm-star")
                            rating = self.extract_star_rating(star_container)
                            review_data[f'{category}评分'] = rating
                        except:
                            review_data[f'{category}评分'] = 0

                        # 提取评论 - 使用多种方法
                        comment_selectors = [
                            "./following-sibling::p[@class='kb-item-msg']",
                            "../p[@class='kb-item-msg']",
                            "./parent::div/p[@class='kb-item-msg']"
                        ]

                        comment_text = ""
                        for comment_selector in comment_selectors:
                            try:
                                comment_elem = category_elem.find_element(By.XPATH, comment_selector)
                                comment_text = comment_elem.text.strip()
                                break
                            except:
                                continue

                        review_data[f'{category}评论'] = comment_text
                    else:
                        review_data[f'{category}评分'] = 0
                        review_data[f'{category}评论'] = ""

                except Exception as e:
                    logging.error(f"提取{category}信息失败: {e}")
                    review_data[f'{category}评分'] = 0
                    review_data[f'{category}评论'] = ""

            return review_data

        except Exception as e:
            logging.error(f"提取评论详情失败: {e}")
            return review_data

    def scrape_review_page(self, review_url):
        """爬取单个评论详情页"""
        try:
            self.driver.get(review_url)
            time.sleep(1)  # 增加等待时间

            # 添加调试
            #self.debug_page_structure()  # 添加这行

            # 等待页面关键元素加载
            try:
                self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "kb-item")))
            except TimeoutException:
                # 如果kb-item没有加载，尝试等待其他关键元素
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".main-series")))
                except TimeoutException:
                    logging.error(f"页面加载超时: {review_url}")
                    return None

            # 提取车辆信息
            car_info = self.extract_car_info()

            # 提取评论详情
            review_details = self.extract_review_details()

            # 提取互动数据（观看数、点赞数、评论数）
            interaction_data = self.extract_interaction_data()

            # 合并数据
            result = {**car_info, **review_details, **interaction_data}
            result['评论链接'] = review_url
            result['爬取时间'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return result

        except Exception as e:
            logging.error(f"爬取评论页面失败 {review_url}: {e}")
            return None

    def extract_purchase_purposes(self, review_elements):
        """从列表页面提取购车目的，为每个评论建立映射"""
        purchase_purposes = []

        try:
            # 查找所有购车目的div
            purpose_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.list_buy_target__rsfaE")

            for purpose_div in purpose_divs:
                try:
                    # 提取购车目的列表
                    purpose_list = purpose_div.find_elements(By.CSS_SELECTOR, "li.list_target__76fWs")
                    purposes = [li.text.strip() for li in purpose_list if li.text.strip()]
                    purchase_purposes.append(", ".join(purposes))
                except Exception as e:
                    logging.warning(f"提取单个购车目的失败: {e}")
                    purchase_purposes.append("")

        except Exception as e:
            logging.error(f"提取购车目的失败: {e}")

        # 如果购车目的数量不足，用空字符串补齐
        while len(purchase_purposes) < len(review_elements):
            purchase_purposes.append("")

        # 如果购车目的数量过多，截取到评论数量
        if len(purchase_purposes) > len(review_elements):
            purchase_purposes = purchase_purposes[:len(review_elements)]

        logging.info(f"提取到{len(purchase_purposes)}个购车目的")
        return purchase_purposes

    def get_review_links_with_purposes(self, car_id, max_pages=1):
        """获取所有评论详情链接，同时获取购车目的"""
        review_data_list = []
        base_url = f"https://k.autohome.com.cn/{car_id}?order=1" #按照发表时间排序

        try:
            self.driver.get(base_url)
            time.sleep(1)

            for page in range(1, max_pages + 1):
                logging.info(f"正在爬取车型{car_id}第{page}页")

                try:
                    # 等待评论列表加载
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".list_nice_value__hI2Bw")))

                    # 查找所有"查看完整口碑"链接
                    detail_links = self.driver.find_elements(By.XPATH, "//a[contains(text(), '查看完整口碑')]")

                    # 提取本页的购车目的
                    purchase_purposes = self.extract_purchase_purposes(detail_links)

                    # 为每个链接分配对应的购车目的
                    for i, link in enumerate(detail_links):
                        href = link.get_attribute('href')
                        if href:
                            purpose = purchase_purposes[i] if i < len(purchase_purposes) else ""
                            review_data_list.append({
                                'link': href,
                                'purchase_purpose': purpose
                            })

                    # 点击下一页
                    if page < max_pages:
                        try:
                            # 尝试多种下一页按钮选择器
                            next_selectors = [
                                "//a[contains(@class, 'athm-page-next')]",
                                "//a[@class='ace-pagination__btn next']",
                                "//a[contains(text(), '下一页')]"
                            ]

                            next_clicked = False
                            for selector in next_selectors:
                                try:
                                    next_button = self.driver.find_element(By.XPATH, selector)
                                    if 'disabled' not in next_button.get_attribute('class'):
                                        next_button.click()
                                        time.sleep(1)
                                        next_clicked = True
                                        break
                                except:
                                    continue

                            if not next_clicked:
                                logging.info("已到达最后一页")
                                break

                        except:
                            logging.info("找不到下一页按钮，可能已到最后一页")
                            break

                except TimeoutException:
                    logging.error(f"页面{page}加载超时")
                    break
                except Exception as e:
                    logging.error(f"爬取第{page}页时出错: {e}")
                    continue

            logging.info(f"车型{car_id}共找到{len(review_data_list)}个评论链接")
            return review_data_list

        except Exception as e:
            logging.error(f"获取评论链接失败: {e}")
            return review_data_list

    def scrape_car_reviews(self, car_id, max_pages=15):
        """爬取指定车型的所有评论"""
        logging.info(f"开始爬取车型{car_id}的评论")

        # 获取所有评论链接和购车目的
        review_data_list = self.get_review_links_with_purposes(car_id, max_pages)

        all_reviews = []
        for i, review_data in enumerate(review_data_list, 1):
            link = review_data['link']
            purchase_purpose = review_data['purchase_purpose']

            logging.info(f"正在爬取第{i}/{len(review_data_list)}个评论")
            review_detail = self.scrape_review_page(link)

            if review_detail:
                # 添加购车目的到评论详情中
                review_detail['购车目的'] = purchase_purpose
                all_reviews.append(review_detail)

                # 打印调试信息
                logging.info(f"成功获取评论信息 - 购车目的: {purchase_purpose}")

            time.sleep(1)  # 增加延时避免被封

        return all_reviews

    def generate_filename(self, ranking, car_name, car_id, timestamp):
        """生成标准化文件名"""
        # 清理车型名称，移除文件名不支持的字符
        clean_car_name = re.sub(r'[<>:"/\\|?*]', '', car_name)
        clean_car_name = clean_car_name.replace(' ', '_')

        # 格式：排名_车型名称_ID_时间戳.csv
        # filename = f"{ranking:03d}_{clean_car_name}_{car_id}_{timestamp}.csv"
        filename = f"{ranking:03d}_{clean_car_name}_{car_id}.csv"  # 不用时间戳
        return filename

    def save_to_csv(self, data, filename):
        """保存数据到CSV文件"""
        if not data:
            logging.warning("没有数据可保存")
            return

        try:
            fieldnames = [
                '车型名称', '车型版本', '发表时间', '行驶里程', '夏季电耗', '春秋电耗', '冬季电耗',
                '夏季续航', '春秋续航', '冬季续航', '百公里油耗', '裸车购买价',
                '购买时间', '购买地点', '最满意', '最不满意',
                '空间评分', '空间评论', '驾驶感受评分', '驾驶感受评论',
                '续航评分', '续航评论', '外观评分', '外观评论',
                '内饰评分', '内饰评论', '性价比评分', '性价比评论',
                '智能化评分', '智能化评论', '油耗评分', '油耗评论',
                '配置评分', '配置评论', '观看数', '点赞数', '评论数',
                '购车目的', '评论链接', '爬取时间'
            ]

            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)

            logging.info(f"数据已保存到 {filepath}")
            return True

        except Exception as e:
            logging.error(f"保存CSV文件失败: {e}")
            return False

    def run_from_csv(self, csv_file="autohome_sales_ranking_id.csv", max_pages=2):
        """从CSV文件读取车型信息并运行爬虫"""
        try:
            # 读取车型信息
            car_info_list = self.load_car_info_from_csv(csv_file)
            if not car_info_list:
                logging.error("没有找到车型信息，程序退出")
                return []

            all_data = []
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 创建进度跟踪文件
            progress_file = os.path.join(self.output_dir, f"progress_{timestamp}.txt")

            for i, car_info in enumerate(car_info_list, 1):
                car_id = car_info['车型ID']
                ranking = car_info['销量排名']
                car_name = car_info['车型名称']

                logging.info(f"开始处理第{i}/{len(car_info_list)}个车型: 排名{ranking} - {car_name} (ID: {car_id})")

                try:
                    # 爬取评论数据
                    reviews = self.scrape_car_reviews(car_id, max_pages)

                    if reviews:
                        all_data.extend(reviews)

                        # 生成文件名并保存单个车型数据
                        filename = self.generate_filename(ranking, car_name, car_id, timestamp)
                        success = self.save_to_csv(reviews, filename)

                        if success:
                            # 记录进度
                            with open(progress_file, 'a', encoding='utf-8') as f:
                                f.write(
                                    f"{datetime.now()}: 完成 {ranking:03d}_{car_name}_{car_id} - 获取{len(reviews)}条评论\n")

                        logging.info(f"车型 {car_name} 完成，获取{len(reviews)}条评论")
                    else:
                        logging.warning(f"车型 {car_name} 没有获取到评论数据")
                        # 记录失败
                        with open(progress_file, 'a', encoding='utf-8') as f:
                            f.write(f"{datetime.now()}: 失败 {ranking:03d}_{car_name}_{car_id} - 无数据\n")

                except Exception as e:
                    logging.error(f"处理车型 {car_name} 时出错: {e}")
                    # 记录错误
                    with open(progress_file, 'a', encoding='utf-8') as f:
                        f.write(f"{datetime.now()}: 错误 {ranking:03d}_{car_name}_{car_id} - {str(e)}\n")
                    continue

            # 保存所有数据汇总
            if all_data:
                summary_filename = f"autohome_reviews_summary_{timestamp}.csv"
                self.save_to_csv(all_data, summary_filename)
                logging.info(f"爬取任务完成，共获得{len(all_data)}条评论数据，汇总保存到 {summary_filename}")

                # 生成统计报告
                self.generate_summary_report(car_info_list, all_data, timestamp)
            else:
                logging.warning("没有获取到任何评论数据")

            return all_data

        except Exception as e:
            logging.error(f"运行爬虫失败: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()

    def generate_summary_report(self, car_info_list, all_data, timestamp):
        """生成汇总报告"""
        try:
            report_file = os.path.join(self.output_dir, f"summary_report_{timestamp}.txt")

            # 统计每个车型的评论数量
            car_review_counts = {}
            for review in all_data:
                car_name = review.get('车型名称', '未知')
                car_review_counts[car_name] = car_review_counts.get(car_name, 0) + 1

            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n")
                f.write("汽车之家口碑评论爬取汇总报告\n")
                f.write("=" * 50 + "\n")
                f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"目标车型总数: {len(car_info_list)}\n")
                f.write(f"成功获取评论的车型数: {len(car_review_counts)}\n")
                f.write(f"总评论数量: {len(all_data)}\n")
                f.write(f"输出目录: {self.output_dir}\n")

                # 统计新增字段
                total_views = sum(review.get('观看数', 0) for review in all_data)
                total_goods = sum(review.get('点赞数', 0) for review in all_data)
                total_comments = sum(review.get('评论数', 0) for review in all_data)
                purpose_count = len([review for review in all_data if review.get('购车目的')])

                f.write(f"总观看数: {total_views}\n")
                f.write(f"总点赞数: {total_goods}\n")
                f.write(f"总评论数: {total_comments}\n")
                f.write(f"包含购车目的的评论数: {purpose_count}\n")

                f.write("\n" + "-" * 30 + "\n")
                f.write("各车型评论统计:\n")
                f.write("-" * 30 + "\n")

                for car_info in car_info_list:
                    car_name = car_info['车型名称']
                    ranking = car_info['销量排名']
                    car_id = car_info['车型ID']
                    count = car_review_counts.get(car_name, 0)
                    f.write(f"排名{ranking:3d}: {car_name} (ID: {car_id}) - {count}条评论\n")

                f.write("\n" + "=" * 50 + "\n")

            logging.info(f"汇总报告已生成: {report_file}")

        except Exception as e:
            logging.error(f"生成汇总报告失败: {e}")


def main():
    """主函数"""
    # 配置参数
    csv_file = "autohome_sales_ranking_id.csv"  # 输入的CSV文件
    max_pages = 25  # 每个车型爬取的最大页数
    output_dir = "autohome_reviews_output"  # 输出目录

    # 检查输入文件是否存在
    if not os.path.exists(csv_file):
        logging.error(f"输入文件 {csv_file} 不存在，请检查文件路径")
        print(f"错误: 找不到输入文件 {csv_file}")
        print("请确保CSV文件包含以下列: 车型ID, 销量排名, 车型名称")
        return

    scraper = AutohomeReviewScraper(output_dir=output_dir)

    try:
        logging.info("=" * 50)
        logging.info("开始执行汽车之家口碑评论爬取任务 - V5增强版")
        logging.info(f"输入文件: {csv_file}")
        logging.info(f"输出目录: {output_dir}")
        logging.info(f"每车型最大页数: {max_pages}")
        logging.info("新增功能: 观看数、点赞数、评论数、购车目的")
        logging.info("=" * 50)

        results = scraper.run_from_csv(csv_file, max_pages)

        logging.info("=" * 50)
        logging.info(f"任务完成，共爬取{len(results)}条评论数据")
        logging.info(f"所有文件已保存到目录: {output_dir}")
        logging.info("=" * 50)

    except KeyboardInterrupt:
        logging.info("用户中断程序")
    except Exception as e:
        logging.error(f"程序执行出错: {e}")
    finally:
        logging.info("程序结束")


if __name__ == "__main__":
    main()