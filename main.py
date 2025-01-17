import selenium.webdriver as webdriver
from time import sleep
from collections.abc import Iterable
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import tomllib
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
from enum import StrEnum
from selenium.webdriver.remote.webelement import WebElement
from datetime import time as Time
import argparse


def str_to_time(time_str: str) -> Time:
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

TODAY = datetime.today()

COURT_LINK_TEXTS = {
    "acer": "Badminton ( Acer ) 55mins",
    "main": "Badminton ( Main ) 55mins",
}


Hall = StrEnum("Hall", "ACER MAIN")
Availability = StrEnum("Availability", "AVAILABLE BOOKED MINE")


class BookingLogs:
    STR_FORMAT = "%d/%m/%y %H:%M"
    filepath: Path
    booked_times: list[datetime]

    def __init__(self, records_file: Path):
        now = datetime.now()
        self.filepath = records_file
        self.booked_times = set([])
        if self.filepath.exists():
            with open(self.filepath, "r") as f:
                for line in f.readlines():
                    line = line.strip()
                    dt = datetime.strptime(line, self.STR_FORMAT)
                    if dt > now:
                        # only add bookings that are in the future
                        self.booked_times.add(dt)

    def write_records(self):
        # write the records to the file
        # sort the dates
        formatted_dates = (dt.strftime(self.STR_FORMAT) for dt in self.booked_times)
        with open(self.filepath, "w") as f:
            for dt in formatted_dates:
                f.write(f"{dt}\n")

    def get_booking_dts(self):
        return self.booked_times.copy()

    def set_booking_dts(self, dts: Iterable[datetime]):
        # remove duplicates
        dts = sorted(list(set(dts)))
        self.booked_times = dts

    def add_dt(self, dt: datetime):
        self.booked_times.add(dt)


def read_config(config_path: Path) -> dict:
    assert config_path.exists(), f"Config file {config_path} does not exist"
    with config_path.open("rb") as f:
        config = tomllib.load(f)
    assert isinstance(config, dict), "Config file is not a valid TOML file"
    return config


def datetime_to_str(dt: datetime, only_date: bool = False) -> str:
    if only_date:
        return dt.strftime("%a %d %b")
    return dt.strftime("%a %d %b %H:%M")


def parse_args():
    parser = argparse.ArgumentParser(description="Booking bot for badminton courts.")
    parser.add_argument(
        "config_filepath",
        type=Path,
        help="Path to the configuration TOML file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = read_config(Path(args.config_filepath))
    booking_logs = BookingLogs(Path(config["paths"]["booking_logs"]))
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--window-size=400,400")
    driver = webdriver.Chrome(options=options)
    driver.get(LOGIN_URL)
    driver.implicitly_wait(3)
    login(
        driver,
        email=config["login-credentials"]["email"],
        password=config["login-credentials"]["password"],
    )

    dates_to_book = [datetime.today() + timedelta(days=delta) for delta in range(8)]
    # remove weekdays closer than 2 days from today
    dates_to_book = [
        date for date in dates_to_book if date.weekday() >= 5 or (date - TODAY).days > 1
    ]
    booked_courts = get_my_bookings(driver)
    for hall, dt in booked_courts:
        print(f"Existing booking at {hall} court at {datetime_to_str(dt)}")
    booked_dts = [dt for _, dt in booked_courts]
    booked_dts.extend(booking_logs.booked_times)
    # remove duplicates
    booked_dts = list(set(booked_dts))

    for hall in Hall:
        go_to_court(driver, hall)
        for date in dates_to_book:
            # check if we already have 2 bookings on this day. if so, continue
            bookings_on_day = [bd for bd in booked_dts if bd.date() == date.date()]
            num_bookings_on_day = len(bookings_on_day)
            # max only book 2 times per day
            if num_bookings_on_day >= 2:
                continue
            # go to the page and look for courts
            navigate_to_date(driver, date)
            court_dts = get_free_courts(driver)
            # filter times when we already have a booking
            # or those within 45  minutes of a booking
            filtered_dts = []
            for court, dt in court_dts:
                conflicting = False
                for booked_dt in booked_dts:
                    if abs(booked_dt - dt) <= timedelta(minutes=45):
                        conflicting = True
                if not conflicting:
                    filtered_dts.append((court, dt))
            # pick a court to book
            court_to_book = pick_court_to_book(
                filtered_dts, is_weekday=date.weekday() < 5
            )
            if court_to_book is None:
                print(
                    f"No courts available for {hall} on {datetime_to_str(date, True)}"
                )
                continue
            book_court(driver, court_to_book[0])
            booked_court_datetime = date.replace(
                hour=court_to_book[1].hour, minute=court_to_book[1].minute
            )
            booked_dts.append(booked_court_datetime)
            print(f"Booked {hall} court at {datetime_to_str(booked_court_datetime)}")
            # navigate back to the court
            go_to_court(driver, hall)
    # once the loop is complete and courts are booked,
    # store the booked_courts
    booking_logs.set_booking_dts(booked_dts)
    booking_logs.write_records()


def parse_court_name(text: str) -> Hall:
    if "Acer" in text:
        return Hall.ACER
    elif "Main" in text:
        return Hall.MAIN
    else:
        raise ValueError("Invalid court name")


def correct_booking_year(booking_date: datetime) -> datetime:
    """Adjust the year of the booking date to be the present year.
    If the booking month is in the past, then we know that the booking is for the next year.
    so we add 1 to the year. Otherwise, we keep the year as the present year.

    Args:
        booking_date (datetime): datetime object of booking

    Returns:
        datetime: adjusted datetime object
    """

    if booking_date.month < TODAY.month:
        booking_date = booking_date.replace(year=TODAY.year + 1)
    else:
        booking_date = booking_date.replace(year=TODAY.year)
    return booking_date


def parse_court_datetime(date_text: str, time_text: str) -> datetime:
    time_text = time_text.split("(")[0].strip()
    date_text = date_text.strip()
    booking_date = datetime.strptime(f"{date_text} {time_text}", r"%a %d %b %H:%M")
    booking_date = correct_booking_year(booking_date)
    return booking_date


def get_my_bookings(driver: WebDriver) -> list[tuple[Hall, datetime]]:
    if driver.current_url != MY_BOOKINGS:
        driver.get(MY_BOOKINGS)
    data_table = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.ID, "ctl00_MainContent_rptMain_ctl01_gvBookings")
        )
    )
    # loop through the rows of the table
    # we know the table has these columns:
    # Activity, Date, Time, Site, Paid, Member, Actions.
    # we only need the first 3
    booked_courts = []
    table_body = data_table.find_element(By.TAG_NAME, "tbody")
    for row in table_body.find_elements(By.TAG_NAME, "tr"):
        columns = row.find_elements(By.TAG_NAME, "td")
        court_name = parse_court_name(columns[0].text)
        court_time = parse_court_datetime(columns[1].text, columns[2].text)
        booked_courts.append((court_name, court_time))
    # go back to the homepage
    driver.get(HOMEPAGE_URL)

    return booked_courts


def get_free_courts(driver) -> list[tuple[WebElement, datetime]]:
    date = get_page_date(driver)
    data_table = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "ctl00_MainContent_grdResourceView"))
    )
    # find all elements with the class itemavailable
    available_courts = data_table.find_elements(By.CLASS_NAME, "itemavailable")
    court_times: list[tuple[WebElement, datetime]] = []
    for court in available_courts:
        inner_element = court.find_element(By.TAG_NAME, "input")
        time_txt = inner_element.get_attribute("value").strip()
        time = datetime.strptime(time_txt, "%H:%M")
        dt = date.replace(hour=time.hour, minute=time.minute)
        court_times.append((inner_element, dt))

    return court_times


def pick_court_to_book(
    courts: list[tuple[WebDriver, datetime]], is_weekday: bool
) -> tuple[WebDriver, datetime]:
    # assume that all the courts are on the same day
    if is_weekday:
        preferences = TIME_PREFERENCES["weekdays"]
    else:
        preferences = TIME_PREFERENCES["weekends"]
    # find the first court that matches the preferences
    for desired_time in preferences:
        for court in courts:
            if court[1].time() == desired_time:
                return court
    return None


def book_court(driver: WebDriver, court: WebElement):
    # navigate to booking page
    court.click()
    # get the element to book
    book_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "ctl00_MainContent_btnBasket"))
    )
    book_button.click()
    # check for completion
    _ = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.CLASS_NAME, "bookingConfirmedContent-content")
        )
    )
    # go home
    driver.get(HOMEPAGE_URL)
    return


def navigate_to_date(driver: WebDriver, target_date: datetime):
    # if we're at the right date, return
    page_date = get_page_date(driver)
    if page_date.date() == target_date.date():
        sleep(1)
        return
    # if the date is more than 7 days in the future, raise an error
    if (target_date - TODAY).days > 7:
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
    page_date_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "ctl00_MainContent_lblCurrentNavDate"))
    )
    page_date = datetime.strptime(page_date_element.text, "%a %d %b")
    page_date = correct_booking_year(page_date)
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
    if driver.current_url != HOMEPAGE_URL:
        driver.get(HOMEPAGE_URL)
    element = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.LINK_TEXT, COURT_LINK_TEXTS[hall]))
    )

    element.click()


if __name__ == "__main__":
    main()
