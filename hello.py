import selenium.webdriver as webdriver
from time import sleep
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import tomllib
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
from enum import StrEnum
from selenium.webdriver.remote.webelement import WebElement
from collections import namedtuple


def str_to_time(time_str: str) -> datetime.time:
    """converts a string in the format HH:MM to a datetime.time object

    Args:
        time_str (str): formatted as HH:MM

    Returns:
        datetime.time: datetime.time object
    """
    return datetime.strptime(time_str, "%H:%M").time()


TIME_PREFERENCES = {
    "weekdays": [str_to_time("07:00"), str_to_time("06:30")],
    "weekends": [
        str_to_time("07:00"),
        str_to_time("07:30"),
        str_to_time("08:00"),
        str_to_time("08:30"),
        str_to_time("09:00"),
        str_to_time("09:30"),
    ],
}
ROOT_URL = "https://oxforduniversity.leisurecloud.net/Connect"
LOGIN_URL = f"{ROOT_URL}/mrmlogin.aspx"
HOMEPAGE_URL = f"{ROOT_URL}/memberHomePage.aspx"
MY_BOOKINGS = f"{ROOT_URL}/mrmViewMyBookings.aspx?showOption=1"


# BADMINTON_ACER_QUICKBOOK_ID = (
#     "ctl00_MainContent_MostRecentBookings1_Bookings_ctl01_bookingLink"
# )
# BADMINTON_MAIN_QUICKBOOK_ID = (
#     "ctl00_MainContent_MostRecentBookings1_Bookings_ctl01_bookingLink"
# )

# BADMINTON_ACER_ID = "ctl00_MainContent__advanceSearchResultsUserControl_Activities_ctrl0_lnkActivitySelect_xs"
# # the id is affected by the window width and view of the page
# # above you can see xs in the end. this could be lg1, xs, sm, md or others based on the window size. so maybe we will search
# # by link text
# BADMINTON_MAIN_ID = "ctl00_MainContent__advanceSearchResultsUserControl_Activities_ctrl1_lnkActivitySelect_xs"

BADMINTON_ACER_LINK_TEXT = "Badminton ( Acer ) 55mins"
COURT_LINK_TEXTS = {
    "Acer": "Badminton ( Acer ) 55mins",
    "Main": "Badminton ( Main ) 55mins",
}


Hall = StrEnum("Hall", "ACER MAIN")
Availability = StrEnum("Availability", "AVAILABLE BOOKED MINE")


# class Court:
#     date: datetime
#     time: datetime
#     hall: Hall
#     availability: Availability
#     element: WebElement

#     def __init__(self, element: WebElement):
#         self.element = element
#         self.date = datetime.strptime(
#             element.find_element(By.CLASS_NAME, "date").text, "%d/%m/%Y"
#         )
#         self.time = datetime.strptime(element.find_element(By.CLASS_NAME, "time"))


def read_config(config_path: Path) -> dict:
    assert config_path.exists(), f"Config file {config_path} does not exist"
    with config_path.open("rb") as f:
        config = tomllib.load(f)
    assert isinstance(config, dict), "Config file is not a valid TOML file"
    return config


def main():
    config = read_config(Path("config.toml"))

    driver = webdriver.Chrome()
    driver.get("https://oxforduniversity.leisurecloud.net/Connect/mrmlogin.aspx")
    driver.implicitly_wait(3)
    login(
        driver,
        email=config["login-credentials"]["email"],
        password=config["login-credentials"]["password"],
    )

    go_to_court(driver, "Acer")

    driver.get(HOMEPAGE_URL)

    # for delta in range(6,7):
    #     # navigate to 7 days later
    #     target_date = datetime.today() + timedelta(days=delta)
    #     is_weekday = target_date.weekday() < 5
    #     navigate_to_date(driver, target_date=target_date)
    #     print("navigated to date")
    #     print(f"{target_date.date()}")

    #     # booked_courts = get_my_booked_courts(driver)
    #     # print(booked_courts)

    #     courts = get_free_courts(driver)
    #     for court in courts:
    #         print(court)
    #     print("picked court")
    #     print(pick_court_to_book(courts, is_weekday=is_weekday))
    


# Court = namedtuple("Court", ["date", "time", "hall", "availability", "element"])

class CourtTime:
    element: WebElement
    time: datetime
    def __init__(self, element: WebElement):
        self.element = element
        self.time = str_to_time(element.get_attribute("value"))
    def __str__(self):
        return f"Time: {self.time}"
    
def get_my_bookings(driver: WebDriver) -> list[CourtTime]:
    if driver.current_url != MY_BOOKINGS:
        driver.get(MY_BOOKINGS)
    data_table = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "ctl00_MainContent_rptMain_ctl01_gvBookings"))
    )
    # loop through the rows of the table
    booked_courts = []
    for row in data_table.find_elements(By.TAG_NAME, "tr"):
        for cell in row.find_elements(By.TAG_NAME, "td"):
            # find the element with the class time
            time_element = cell.find_element(By.CLASS_NAME, "time")
            booked_courts.append(str_to_time(time_element.text))


    

def get_free_courts(driver) -> list[CourtTime]: 
    data_table = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "ctl00_MainContent_grdResourceView"))
    )
    # find all elements with the class itemavailable
    available_courts = data_table.find_elements(By.CLASS_NAME, "itemavailable")
    # get the item within which is an input element
    available_courts = [
        CourtTime(court.find_element(By.TAG_NAME, "input")) for court in available_courts
    ]
    # filter out the courts for which that time is already booked by me
    booked_court_times = get_my_booked_courts(driver)
    available_courts = [
        court for court in available_courts if court.time not in booked_court_times
    ]

    return available_courts


def pick_court_to_book(courts:list[CourtTime], is_weekday: bool) -> CourtTime:
    # assume that all the courts are on the same day
    if is_weekday:
        preferences = TIME_PREFERENCES["weekdays"]
    else:
        preferences = TIME_PREFERENCES["weekends"]
    # find the first court that matches the preferences
    for desired_time in preferences:
        for court in courts:
            if court.time == desired_time:

                return court
        
    
def get_my_booked_courts(driver) -> list[datetime]:
    data_table = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "ctl00_MainContent_grdResourceView"))
    )
    # find all elements with the class itemavailable
    booked_courts = data_table.find_elements(By.CLASS_NAME, "itemofcurrentuser")
    times = [
        str_to_time(court.find_element(By.CLASS_NAME, "btn").text)
        for court in booked_courts
    ]
    return times


def navigate_to_date(driver: WebDriver, target_date: datetime):
    # if we're at the right date, return
    page_date = get_page_date(driver)
    if page_date.date() == target_date.date():
        return
    # if the date is more than 7 days in the future, raise an error
    if (target_date - datetime.today()).days > 7:
        raise ValueError("Date is more than 7 days in the future")

    target_date_in_future = target_date > page_date
    # get the date picker
    if target_date_in_future:
        button_name = "ctl00_MainContent_Button2"
    else:
        button_name = "ctl00_MainContent_Button1"

    nav_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, button_name))
    )
    nav_button.click()
    sleep(1)
    navigate_to_date(driver, target_date)


def get_page_date(driver: WebDriver) -> datetime:
    today = datetime.today()
    page_date_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "ctl00_MainContent_lblCurrentNavDate"))
    )
    page_date = datetime.strptime(page_date_element.text, "%a %d %b")
    # edge case where the date is in the next year
    if page_date.month < today.month:
        page_date = page_date.replace(year=today.year + 1)
    else:
        page_date = page_date.replace(year=today.year)
    return page_date


def login(driver: WebDriver, email: str, password: str):
    email_box = driver.find_element(by=By.ID, value="ctl00_MainContent_InputLogin")
    password_box = driver.find_element(
        by=By.ID, value="ctl00_MainContent_InputPassword"
    )

    email_box.send_keys(email)
    password_box.send_keys(password)

    submit_button = driver.find_element(by=By.ID, value="ctl00_MainContent_btnLogin")
    # wait for the page to load
    submit_button.click()


def go_to_court(driver: WebDriver, hall: Hall):
    element = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.LINK_TEXT, COURT_LINK_TEXTS[hall]))
    )

    element.click()


if __name__ == "__main__":
    main()
