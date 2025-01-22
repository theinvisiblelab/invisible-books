import argparse
from datetime import datetime
import json
import os
import re
import time
from urllib.request import urlopen
from urllib.error import HTTPError
import bs4
import pandas as pd
import requests
from bs4 import BeautifulSoup

def get_goodreads_info(isbn):
    url = f"https://www.goodreads.com/search?q={isbn}"
    return url

def get_genres(soup):
    genres_div = soup.find("div", {"data-testid": "genresList"})
    if genres_div:
        genre_links = genres_div.find_all("a", class_="Button--tag-inline")
        genres = [link.text.strip() for link in genre_links]
        return genres
    else:
        return []

def get_series_name(soup):
    series = soup.find(id="bookSeries").find("a")
    if series:
        series_name = re.search(r'\((.*?)\)', series.text).group(1)
        return series_name
    else:
        return ""

def get_series_uri(soup):
    series = soup.find(id="bookSeries").find("a")
    if series:
        series_uri = series.get("href")
        return series_uri
    else:
        return ""

def get_publication_info(soup):
    publication_info_list = []
    a = soup.find_all('div', class_='FeaturedDetails')
    for item in a:
        publication_info = item.find('p', {'data-testid': 'publicationInfo'}).text
        publication_info_list.append(publication_info)
    return publication_info_list

def get_num_pages(soup):
    number_of_pages_list = []
    featured_details = soup.find_all('div', class_='FeaturedDetails')
    for item in featured_details:
        format_info = item.find('p', {'data-testid': 'pagesFormat'})
        if format_info:
            format_text = format_info.text
            parts = format_text.split(', ')
            if len(parts) == 2:
                number_of_pages, _ = parts
                number_of_pages = ''.join(filter(str.isdigit, number_of_pages))
                number_of_pages_list.append(number_of_pages)
            elif len(parts) == 1:
                if parts[0].isdigit():
                    number_of_pages_list.append(parts[0])
                else:
                    number_of_pages_list.append(None)
            else:
                number_of_pages_list.append(None)
        else:
            number_of_pages_list.append(None)
    return number_of_pages_list

def get_format_info(soup):
    format_info_list = []
    a = soup.find_all('div', class_='FeaturedDetails')
    for item in a:
        format_info = item.find('p', {'data-testid': 'pagesFormat'}).text
        format_info_list.append(format_info)
    return format_info_list

def get_rating_distribution(soup):
    rating_numbers = {}
    try:
        rating_bars = soup.find_all('div', class_='RatingsHistogram__bar')
        for rating_bar in rating_bars:
            try:
                rating = rating_bar['aria-label'].split()[0]
                label_total = rating_bar.find('div', class_='RatingsHistogram__labelTotal')
                num_ratings = label_total.get_text().split(' ')[0]
                rating_numbers[rating] = num_ratings
            except (KeyError, IndexError) as e:
                print(f"Error occurred while extracting rating number for {rating}: {e}")
                rating_numbers[rating] = '0'
    except AttributeError as e:
        print(f"Error occurred while finding rating bars: {e}")
    return rating_numbers

def get_cover_image_uri(soup):
    series = soup.find('img', class_='ResponsiveImage')
    if series:
        series_uri = series.get('src')
        return series_uri
    else:
        return ""

def book_details(soup):
    try:
        return soup.find('div', class_='DetailsLayoutRightParagraph').text
    except:
        return ' '

def contributor_info(soup):
    contributor = soup.find('a', {'class': 'ContributorLink'})
    return contributor

def scrape_book(isbn):
    book_url = get_goodreads_info(isbn)
    if not book_url:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        print(f"Scraping book details from: {book_url}")
        time.sleep(2)  # Rate-limiting

        response = requests.get(book_url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to retrieve book page. HTTP Status: {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        book_data = {
            'isbn': isbn,
            'book_url': book_url,
            'title': ' '.join(soup.find('h1', {'data-testid': 'bookTitle'}).text.split()),
            'author': contributor_info(soup).find('span', {'class': 'ContributorLink__name'}).text.strip(),
            'authorlink': contributor_info(soup)['href'],
            'average_rating': soup.find('div', {'class': 'RatingStatistics__rating'}).text.strip(),
            'num_pages': get_num_pages(soup),
            'genres': get_genres(soup),
            'publication_info': get_publication_info(soup),
            'format': get_format_info(soup),
            'rating_distribution': get_rating_distribution(soup),
            'cover_image_uri': get_cover_image_uri(soup),
            'book_details': book_details(soup)
        }

        print(f"Scraped data for ISBN {isbn}: {book_data}")
        return book_data
    except Exception as e:
        print(f"Failed to scrape book for ISBN {isbn}: {e}")
        return None

def main():
    start_time = datetime.now()
    parser = argparse.ArgumentParser()
    parser.add_argument('--isbn_list_path', type=str, required=True, help="Path to a file containing ISBNs (one per line)")
    parser.add_argument('--output_directory_path', type=str, required=True, help="Output directory path")
    parser.add_argument('--format', type=str, choices=['json', 'csv'], default='json', help="Output format (json or csv)")
    args = parser.parse_args()

    if not os.path.exists(args.output_directory_path):
        os.makedirs(args.output_directory_path)

    with open(args.isbn_list_path, 'r') as f:
        isbn_list = [line.strip() for line in f if line.strip()]

    print(f"ISBNs to scrape: {isbn_list}")

    books = []
    for i, isbn in enumerate(isbn_list):
        print(f"Scraping book {i + 1}/{len(isbn_list)}: {isbn}")
        book_data = scrape_book(isbn)
        if book_data:
            books.append(book_data)

    output_path = os.path.join(args.output_directory_path, 'all_books')
    if args.format == 'json':
        with open(f"{output_path}.json", 'w') as f:
            json.dump(books, f, indent=4)
        print(f"Books saved to {output_path}.json")
    elif args.format == 'csv':
        books_df = pd.DataFrame(books)
        books_df.to_csv(f"{output_path}.csv", index=False)
        print(f"Books saved to {output_path}.csv")

    print(f"Scraping completed in {datetime.now() - start_time}")

if __name__ == '__main__':
    main()