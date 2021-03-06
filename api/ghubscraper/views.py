"""This module contains the app's views."""

import datetime
import os

import requests
from django.db.models import Avg
from django.shortcuts import redirect
from rest_framework import generics, status
from rest_framework.response import Response

from .models import Repo
from .serializers import AccountSerializer, CrawlSerializer, RepoSerializer


# use CreateAPIView for default form value
class AddRepo(generics.CreateAPIView):
    """View that adds repo data to the database."""

    serializer_class = RepoSerializer

    def get(self, request):
        """Return usage info message."""
        return Response(
            {
                "info": "Make a POST request against this endpoint (/add/) to add new repo data."
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """Save request data to the database."""
        # use many=False since only single object is expected
        serializer = RepoSerializer(data=request.data, many=False)
        data = request.data
        data["account"] = clean_url(data["account"])
        if serializer.is_valid():

            # drop existing items
            queryset = Repo.objects.filter(account=data["account"], repo=data["repo"])
            if queryset:
                for record in queryset:
                    record.delete()

            # save new item
            instance = Repo(**data)
            instance.account = data["account"]
            instance.save()

            return Response(data=data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CrawlPages(generics.CreateAPIView):
    """View that starts scraping by calling spiders deployed on a remote server."""

    serializer_class = CrawlSerializer

    def get(self, request):
        """Return usage info message."""
        return Response(
            {
                "info": "Make a POST request against this endpoint (/crawl/) to start crawling."
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """Start scraping process on remote server by providing a list of urls to scrape."""

        serializer = CrawlSerializer(data=request.data, many=False)
        if not request.data["start_urls"]:
            return Response("No URLs have been provided.", status.HTTP_400_BAD_REQUEST)

        if serializer.is_valid():
            validated_urls = []
            for url in request.data["start_urls"]:
                validated_urls.append(cleaned_url := clean_url(url))

                # drop existing items
                queryset = Repo.objects.filter(account=cleaned_url)
                if queryset:
                    for record in queryset:
                        record.delete()

            # remove duplicates
            request.data["start_urls"] = list(set(validated_urls))

            response = requests.post(
                (os.getenv("SCRAPYD_HOST") or "http://scrapyd:6800") + "/schedule.json",
                data={
                    "start_urls": ",".join(request.data["start_urls"]),
                    "project": "scraper",
                    "spider": "scraper_api",
                    "jobid": datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S"),
                },
            )
            if response.status_code == 200:
                return Response(request.data, status=status.HTTP_200_OK)

            return Response(
                "Error connecting to scrapyd server.", status.HTTP_400_BAD_REQUEST
            )

        return Response(
            "All URLs must be of the following format: "
            "http(s)://github.com/<account>(/)",
            status=status.HTTP_400_BAD_REQUEST,
        )


class ListAccounts(generics.ListAPIView):
    """Show all scraped accounts."""

    serializer_class = RepoSerializer

    def get(self, request):
        """Get a list of scraped accounts."""
        queryset = set(item["account"] for item in Repo.objects.values("account"))
        return Response({"accounts": sorted(list(queryset))}, status=status.HTTP_200_OK)


class Index(generics.ListAPIView):
    """Index view."""

    def get(self, request):
        """Redirect to the list_accounts view."""
        return redirect("list_accounts")


class Stats(generics.ListAPIView):
    """View that provides aggregated stats on stored GitHub data."""

    serializer_class = AccountSerializer

    def get(self, request):
        """Get info about all stored GitHub accounts."""
        queryset = Repo.objects.values("account", "repo")
        return Response(
            {
                "account_count": (
                    account_count := queryset.values("account").distinct().count()
                ),
                "repo_count": (repo_count := queryset.count()),
                "avg_repo_count": repo_count / account_count if account_count else 0,
            }
        )

    def post(self, request):
        """Request info on a specific GitHub account."""
        serializer = AccountSerializer(data=request.data, many=False)
        if not request.data["account"]:
            return Response(
                "No account URL has been provided.", status.HTTP_400_BAD_REQUEST
            )
        if serializer.is_valid():
            cleaned_account = clean_url(request.data["account"])
            queryset = Repo.objects.filter(account=cleaned_account)
            if queryset:
                max_commit_count = max(
                    item["main_branch_commit_count"]
                    if item["main_branch_commit_count"] is not None
                    else 0
                    for item in queryset.values("main_branch_commit_count")
                )

                top_repos_by_commit_count = queryset.filter(
                    main_branch_commit_count=max_commit_count
                ).values("repo")

                # handles repos with the same commit count
                top_repos_by_commit_count = [
                    item["repo"] for item in top_repos_by_commit_count
                ]

                avg_stars_count = queryset.values("stars").aggregate(
                    avg_stars_count=Avg("stars")
                )["avg_stars_count"]
                return Response(
                    {
                        "top_repos_by_commit_count": top_repos_by_commit_count,
                        "commit_count": max_commit_count,
                        "avg_stars_count": avg_stars_count,
                    }
                )
            return Response(
                "This account has not been crawled yet.", status=status.HTTP_200_OK
            )

        return Response(
            "Account URLs must be of the following format: "
            "http(s)://github.com/<account>(/)",
            status=status.HTTP_400_BAD_REQUEST,
        )


def clean_url(url: str) -> str:
    """Transform urls to a standard form."""
    url = url.replace("http:", "https:")
    return url[:-1] if url[-1] == "/" else url
