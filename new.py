
import time
import csv
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import re

CSV_FILENAME = "car_data.csv"
SAVE_INTERVAL = 20  # Save data after every 20 cars

# Set up Selenium driver
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    service = Service()
    return webdriver.Chrome(service=service, options=chrome_options)

# Function to scroll and load all cars
def load_all_cars(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

# Function to scrape car details page
def get_car_details(url: str) -> dict:
    driver = get_driver()
    driver.get(url)
    time.sleep(5)
    details = {}

    def extract_text(xpath):
        try:
            return driver.find_element(By.XPATH, xpath).text.strip()
        except:
            return "Not Available"

    details["Price"] = extract_text("//div[contains(text(), '₹')]")
    details["Kilometers Driven"] = extract_text("//div[contains(text(), 'km')]")
    details["Transmission"] = extract_text("//div[contains(text(), 'Manual') or contains(text(), 'Automatic')]")
    details["Fuel Type"] = extract_text("//div[contains(text(), 'Petrol') or contains(text(), 'Diesel') or contains(text(), 'CNG') or contains(text(), 'Electric')]")
    details["Manufacturing Year"] = extract_text("//span[contains(text(), 'Manufacturing year')]/../../div[last()]")
    details["Number of Owners"] = extract_text("//span[contains(text(), 'Owner') or contains(text(), 'owners')]/../../div[last()]")
    details["Color"] = extract_text("//span[contains(text(), 'Color')]/../../div[last()]")
    details["Car Available At"] = extract_text("//span[contains(text(), 'Available')]/../../div[last()]")
    details["Insurance"] = extract_text("//span[contains(text(), 'Insurance')]/../../div[last()]")
    details["Registration"] = extract_text("//span[contains(text(), 'Registration')]/../../div[last()]")
    
    driver.quit()
    return details

# Function to scrape car names from listing page
def get_car_list(base_url):
    driver = get_driver()
    driver.get(base_url)
    time.sleep(5)
    load_all_cars(driver)  # Ensure all listings are loaded
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()
    
    car_list = []
    car_elements = soup.find_all("li", class_="o-C o-jA o-co o-bS")
    
    for car in car_elements:
        try:
            car_name_element = car.find("h3")
            car_link_element = car.find("a")
            if car_name_element and car_link_element:
                car_name = car_name_element.text.strip()
                car_url = "https://www.carwale.com" + car_link_element["href"]
                car_list.append((car_name, car_url))
        except AttributeError:
            continue
    
    return car_list

# Function to get list of cities already scraped in CSV
def get_scraped_cities_from_csv():
    scraped_cities = set()
    try:
        with open(CSV_FILENAME, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = row["City"].strip().lower()
                scraped_cities.add(city)
    except FileNotFoundError:
        pass
    return scraped_cities

# Get prioritized list of cities
def get_cities():
    priority_order = [
        "mumbai", "bangalore", "hyderabad", "pune",
        "delhi", "gurgaon", "gurugram", "noida", "faridabad", "ghaziabad", "meerut",
        "lucknow", "nashik", "nagpur", "kerala", "trivandrum", "patna"
    ]

    with open("car_list.txt", "r", encoding="utf-8") as f:
        all_city_lines = f.readlines()

    city_map = {}  # cleaned_name -> original
    for line in all_city_lines:
        city_raw = line.split(',')[0].strip()
        cleaned_city = re.sub(r'[^a-zA-Z]', '', city_raw.lower())
        city_map[cleaned_city] = city_raw

    scraped_cities = get_scraped_cities_from_csv()

    # Prioritized cities first
    prioritized = [city for city in priority_order if city in city_map and city not in scraped_cities]
    remaining = [c for c in city_map.keys() if c not in priority_order and c not in scraped_cities]

    return prioritized + remaining

# Save car data to CSV
def save_to_csv(data):
    mode = "a"
    with open(CSV_FILENAME, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["City", "Car Name", "Price", "Kilometers Driven", "Transmission", "Fuel Type", "Manufacturing Year", "Number of Owners", "Color", "Car Available At", "Insurance", "Registration", "URL"])
        if f.tell() == 0:
            writer.writeheader()
        writer.writerows(data)
    print(f"✅ Saved {len(data)} records to {CSV_FILENAME}")

# Main function to scrape and save data
def scrape_and_save():
    cities = get_cities()
    for city in cities:
        print(f"🔍 Scraping data for {city}...")
        base_url = f"https://www.carwale.com/used/{city}/"
        try:
            cars = get_car_list(base_url)
        except Exception as e:
            print(f"❌ Failed to load cars for {city}: {e}")
            continue

        all_car_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(lambda car: (car[0], car[1], get_car_details(car[1])), cars)

            for index, (car_name, car_url, details) in enumerate(results, start=1):
                car_data = {"City": city.capitalize(), "Car Name": car_name, "URL": car_url, **details}
                all_car_data.append(car_data)

                if index % SAVE_INTERVAL == 0:
                    save_to_csv(all_car_data)
                    all_car_data.clear()
        
        if all_car_data:
            save_to_csv(all_car_data)

if __name__ == "__main__":
    scrape_and_save()
    print("✅ Scraping complete! Data saved.")
