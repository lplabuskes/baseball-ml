from typing import List, Tuple
from baseball_types import OddsOutcome
import time
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

import re


ODDS_BOX_CLASS = "next-m:min-w-[80%] next-m:min-h-[26px] next-m:max-h-[26px] flex cursor-pointer items-center justify-center font-bold hover:border hover:border-orange-main min-w-[50px] min-h-[50px]"
DATA_TABLE_CLASS = "flex flex-col px-3 text-sm max-mm:px-0"


# Website I'm using has a delay that prevents `requests` from working
def grab_html(url: str):
    driver = webdriver.Chrome()
    driver.get(url)
    html = ""
    try:
        _ = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f"[class='{DATA_TABLE_CLASS}']"))
        )
        time.sleep(5)  # not happy about needing the fudge factor, but it is what it is
        html = driver.page_source
    finally:
        driver.quit()
    return html


def available_years(html: str) -> List[str]:
    pattern = re.compile("https://www.oddsportal.com/baseball/usa/mlb-(20\d\d)/results/")
    return list(set(pattern.findall(html)))


def last_page(html: str) -> int:
    pattern = re.compile('class="pagination-link" data-number="(\d+)"')
    return max([int(n) for n in pattern.findall(html)])


def lines_to_pcts(line1: int, line2: int) -> Tuple[float, float]:
    pct1 = 100/(100+line1) if line1 > 0 else -line1/(100-line1)
    pct2 = 100/(100+line2) if line2 > 0 else -line2/(100-line2)
    tot = pct1 + pct2
    pct1 /= tot
    pct2 /= tot
    return pct1, pct2


def parse_odds_page(html: str) -> List[OddsOutcome]:
    soup = BeautifulSoup(html, "html.parser")
    odds_boxes = soup.find_all(class_=ODDS_BOX_CLASS)
    it = iter(odds_boxes)
    outcomes = []

    for box in it:
        outcome = OddsOutcome()
        box_home = next(box.children)
        box_away = next(next(it).children)

        outcome.home_team_won = "gradient-green" in box_home["class"]
        home_line = int(box_home.text)
        away_line = int(box_away.text)
        home_pct, away_pct = lines_to_pcts(home_line, away_line)
        outcome.home_implied_odds = home_pct
        outcome.home_line = home_line
        outcome.away_implied_odds = away_pct
        outcome.away_line = away_line
        outcomes.append(outcome)
    
    return outcomes


def walk_odds_site():
    DIR = "C:\\Users\\lplab\\Documents\\Retrosheet\\odds"
    BASE_URL = "https://www.oddsportal.com/baseball/usa/"
    if not os.path.exists(DIR):
        os.makedirs(DIR)
    html = grab_html(BASE_URL + "mlb/results/")
    years = available_years(html)
    for year in years:
        html = grab_html(BASE_URL + f"mlb-{year}/results/")
        n_pages = last_page(html)
        # In hindsight, I could do this by having Selenium click the next button
        # But I can also just run this while I sleep
        for i in range(n_pages):
            fname = f"odds_{year}_{i+1:02}.html"
            if os.path.exists(os.path.join(DIR, fname)):
                continue
            else:
                html = grab_html(BASE_URL + f"mlb-{year}/results/#/page/{i+1}/")
                with open(os.path.join(DIR, fname), "w", encoding="utf-16") as file:
                    file.write(html)


if __name__ == "__main__":
    walk_odds_site()
