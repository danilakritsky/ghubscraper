ghubscraper
============

A small dockerized service that scrapes GitHub account pages, collecting info about accounts' repos and providing summary statistics.


## Architecture
**ghubscraper** consists of 6 dockerized services that are run together with `docker-compose`.
1. ***scraper*** - contains `scrapy` project and spiders that crawl and parse GitHub account pages for data. Two spiders are defined:
    - *scraper_mongo_spider* - scrapes data and saves them to a MongoDB instance running on ***mongo*** container
    - *scraper_api_spider* - scrapes the same data as the previous spider, but saves it to a PostgreSQL instance by making requests to a specialized web app running on the ***api*** container

    The main task of this service is to deploy these spiders to a remote `scrapyd` server running on ***scrapyd*** container to allow remote scheduling of spiders by sending post requests to the server.

2. ***api*** - a dockerized Django Rest Framework app connected to a Postgres database running on ***postgres*** container. API supports adding new repo items to the database, listing all accounts that have been scraped, starting remote jobs on ***scrapyd*** server and getting summary statistics on stored data.

3. ***scrapyd*** - a web server that enables remote scheduling of `scrapy` spiders. Spiders defined in ***scraper*** are deployed here.

4. ***scrapydweb*** - an app that provides web UI to the ***scrapyd*** service for easier spider scheduling and logging.

5. ***mongo*** - an instance of MondoDB used to store items scraped by *scraper_mongo_spider*.

6. ***postgres*** - an instance of PostgreSQL database used to store items scraped by *scraper_api_spider* through the ***api*** service.

Items saved to the ***mongo*** and ***postgres*** databases persist across container sessions by using mapped volumes inside the project's directory.



## Deployment
**`docker` and `docker-compose` must be available on your system.**  
Clone the project and `cd` into it:
> `git clone https://github.com/danilakritsky/ghubscraper`
>
> `cd ghubscraper`
>
Start containers in detached mode:
> `docker-compose up -d`

## Example usage

### Using the **api** service for scraping data and statistics
Browsable API can be accessed on **localhost:8000** and provides the following actionable endpoints with the ability to POST test data:
- GET *localhost:8000/accounts/* - list all accounts that have been scraped and saved to the Postgres database.  
Example response:  
>`{
    "accounts": [
        "https://github.com/danilakritsky",
        "https://github.com/scrapy",
        "https://github.com/shurke",
        "https://github.com/ubuntu"
    ]
}`
>

- POST *localhost:8000/add/* - send POST request to save data about a repo to the database.  
Example request data:
> `{
    "account": "https://github.com/ubuntu",
    "repo": "ubuntu-make",
    "about": "Easy setup of common tools for developers on Ubuntu.",
    "website_link": "",
    "stars": 1091,
    "forks": 176,
    "watching": "75",
    "main_branch_commit_count": 1799,
    "main_branch_latest_commit_author": "LyzardKing",
    "main_branch_latest_commit_datetime": "2022-01-29T13:35:02Z",
    "main_branch_latest_commit_message": "Fix AdoptOpenJDK to adoptium",
    "release_count": 4,
    "latest_release_tag": "21.10",
    "latest_release_datetime": "2022-01-29T13:35:02Z",
    "latest_release_changelog": ""
}
`
>
- POST *localhost:8000/crawl/* - start remote spider job on ***scrapyd*** server, crawling the provided urls.  
Example request data:
>`{
    "start_urls": [
        "https://github.com/danilakritsky",
        "https://github.com/scrapy"
    ]
}`
>
- GET *localhost:8000/stats/* - get summary data on all stored accounts. Example:
> `{
"account_count": 4, "repo_count": 125, "avg_repo_count": 31.25}`

- POST *localhost:8000/stats/* - request must provide an account URL and response will contain summary info about this account. Example request data:
>`{
"account": "http://github.com/scrapy"
}`
>
Example response:  
> `{
"top_repos_by_commit_count": [
    "base-chromium"
],
"commit_count": 15783,
"avg_stars_count": 2041.1153846153845
}`
        
### Using **scrapyd** and **scrapydweb** to manage spiders
**scrapyd** is running on *localhost:6800* and provides minimal interface to scheduling spider jobs and managing logs.  
**scrapydweb** service is running on *localhost:5000* and provides a friendlier alternative to managing spiders deployed on  **scrapyd**.  
Learn more about **scrapydweb** [here](https://github.com/my8100/scrapydweb).  
**!!!** When scheduling jobs don't forget to pass the `start_urls` argument:  
> `curl http://scrapyd:6800/schedule.json -d project=scraper -d spider=scraper_api
-d start_urls=https://github.com/{ACCOUNT_TO_SCRAPE}`

### Dispatching spiders from the **scraper** container 
First, login in into the `scraper` container by running:
> `docker exec -it scraper sh`  
>
When logged in use the following command to scrape *specific account*:
> `scrapy crawl <spider> -a start_urls=https://github.com/{ACCOUNT_TO_SCRAPE}`
>
Example:
> `scrapy crawl <spider> -a start_urls=https://github.com/danilakritsky`
>
To scrape *multiple accounts* pass a comma delimited list of urls to the `start_urls` parameter:
> `scrapy crawl <spider> -a start_urls=https://github.com/danilakritsky,https://github.com/scrapy`
>

To scrape accounts *without logging* into the `scraper` container use:
>`docker exec scraper  sh -c 'scrapy crawl scraper -a start_urls=https://github.com/danilakritsky,https://github.com/scrapy'`
>

### Examining stored data
To examine the data stored in *MongoDB* login into the **mongo** container's shell by running:
> `docker exec -it mongo sh`  
>
Then use the following command to open the mongo shell:
> `mongosh --username ghubscraper --password ghubscraper`
>
Or skip logging into the container's shell and login to `mongosh` directly from host by running:
> `docker exec -it mongo sh -c 'mongosh --username ghubscraper --password ghubscraper'`
>
After logging in you can examine the stored data by running the following commands:
> `use ghubscraper` 
>
>`db.repos.find()`
>
To view data stored in **postgres**, first login to the container:  
> `docker exec -it postgres sh`  
>
In container run the following command to open postgres shell:
> `psql -U postgres`
>
When in postgres shell run the following commands to view stored items:
> `\c ghubscraper`  
>  `SELECT * FROM ghubscraper_repo;`

### Stopping services
To stop all containers run:
> `docker-compose down`
>

### Troubleshooting
If some errors arise and persist - stop the services and try removing all containers and images via `docker <container|image> prune` and `docker image rmi` commands.  
Then rebuild images with `docker build --no-cache <image>` and restart the services with `docker-compose up -d`.  

Happy scraping:)