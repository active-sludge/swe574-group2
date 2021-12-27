import random

from django.contrib.auth.models import User
from django.db.models import Count
from enum import Enum
from wikodeApp.models import Activity, Article, Tag, Annotation, FollowRelation, TagRelation, Author
from wikodeApp.utils.activityManager import ActivityManager
from wikodeApp.utils.articleSuggestionDTO import ArticleSuggestionDTO
from wikodeApp.utils.followManager import getFollowerList, getFolloweeList


class ArticleSuggestionRatings(Enum):
    viewed_by_followee = 6
    most_viewed_article = 4
    tagged_by_followee = 8
    recently_tagged = 3
    other_tagged_articles = 9


class SuggestionManager:
    # Limit for suggestion list
    # Upon reach, the manger will stop finding more suggestions
    suggestion_limit = 3

    def __init__(self, user_id):
        owner = User.objects.get(id=user_id)
        self.user_id = user_id
        self.article_list = []
        self.article_id_list = []
        if owner:
            self.owner = owner
            self.followers = getFollowerList(owner)
            self.followees = getFolloweeList(owner)

    # Ultimate method to get article suggestions
    # returns until "suggestion_limit" is reached.
    # gets random articles if the logic is not sufficient
    def get_article_suggestion(self):
        self.article_list.append(self.get_other_tagged_articles())
        if len(self.article_list) >= self.suggestion_limit:
            return self.article_list

        tagged_articles_from_followee = self.get_tagged_articles_from_followee()
        if tagged_articles_from_followee:
            self.article_list.append(self.get_tagged_articles_from_followee())
            if len(self.article_list) >= self.suggestion_limit:
                return self.article_list

        viewed_article_suggestion_from_followee = self.get_viewed_article_suggestion_from_followee()
        if viewed_article_suggestion_from_followee:
            self.article_list.append(self.get_viewed_article_suggestion_from_followee())
            if len(self.article_list) >= self.suggestion_limit:
                return self.article_list

        most_viewed_article = self.get_most_viewed_article()
        if most_viewed_article:
            self.article_list.append(self.get_most_viewed_article())
            if len(self.article_list) >= self.suggestion_limit:
                return self.article_list

        recently_tagged_article = self.get_recently_tagged_article()
        if recently_tagged_article:
            self.article_list.append(self.get_recently_tagged_article())

        self.get_random_article()
        return self.article_list

    # Gets viewed articles from followee
    # excludes owner's already viewed articles
    def get_viewed_article_suggestion_from_followee(self):
        article_list = self.get_article_id_list_from_followee(activity_type=1)
        return article_list

    # Gets the most viewed article (1)
    # chekcs if the owner has already seen it
    def get_most_viewed_article(self):
        most_common = \
        Activity.objects.filter(activity_type=1, target_type=3).annotate(mc=Count('target_id')).order_by('-mc')[0]
        if most_common:
            viewed_article_id_list = self.get_my_viewed_id_list()
            if most_common.target_id in viewed_article_id_list:
                return
            else:

                if most_common.target_id in self.article_id_list:
                    return
                else:
                    article = Article.objects.get(id=most_common.target_id)
                    self.article_id_list.append(most_common.target_id)
                    return article

    # Gets tagged articles from followee
    # excludes owner's already viewed articles
    def get_tagged_articles_from_followee(self):
        article_list = self.get_article_id_list_from_followee(activity_type=6)
        return article_list

    # Gets recently tagged articles from everyone
    # excludes owner's already viewed articles
    def get_recently_tagged_article(self):
        latest_tagged_article_list = []
        tagged_article = Activity.objects.filter(activity_type=6, target_type=3).order_by('-id')
        latest_tagged_article_list.append(tagged_article[0].target_id)
        unique_list = self.substract_viewed_articles(id_list=list(latest_tagged_article_list))
        article_list = []
        for id in unique_list:

            if id in self.article_id_list:
                continue
            else:
                article = Article.objects.get(id=id)
                article_list.append(article)
                self.article_id_list.append(id)
        return article_list

    # Gets other articles that is tagged with same tags
    # excludes owner's already viewed articles
    def get_other_tagged_articles(self):
        my_tags = TagRelation.objects.filter(tagger=self.owner)
        my_tags_id_list = []
        for tag in my_tags:
            if tag.tag_id in my_tags_id_list:
                continue
            else:
                my_tags_id_list.append(tag.tag_id)

        articles_with_my_tags = TagRelation.objects.filter(tag_id__in=my_tags_id_list).exclude(tagger=self.owner)

        article_id_list = []
        for tag in articles_with_my_tags:
            article_id_list.append(tag.article_id)

        article_list = []
        for id in article_id_list:
            if id in self.article_id_list:
                continue
            else:
                article = Article.objects.get(id=id)
                article_list.append(article)
                self.article_id_list.append(id)

        return article_list

    # Returns an article list from followee
    # depending on activity type
    def get_article_id_list_from_followee(self, activity_type):
        article_id_list = []
        if self.followees:
            for followee in self.followees:
                if followee:
                    followee_list = Activity.objects.filter(user_id=followee[0], activity_type=activity_type,
                                                            target_type=3)
                    for x in followee_list:
                        if x:
                            article_id_list.append(x.target_id)

        article_id_list = self.substract_viewed_articles(id_list=article_id_list)

        article_list = self.get_articles_from_id_list(id_list=article_id_list)
        return article_list

    # Returns owner's already viewed article list
    def get_my_viewed_id_list(self):
        viewed_article_id_list = []
        my_viewed_list = Activity.objects.filter(user_id=self.user_id, activity_type=1, target_type=3)
        for viewed in my_viewed_list:
            if viewed:
                if viewed.target_id in viewed_article_id_list:
                    continue
                else:
                    viewed_article_id_list.append(viewed.target_id)
        return viewed_article_id_list

    # Returns an article list, from a given id list
    def get_articles_from_id_list(self, id_list):
        article_list = []
        for id in id_list:
            if id in self.article_id_list:
                continue
            else:
                article = Article.objects.get(id=id)
                article_list.append(article)
                self.article_id_list.append(id)
        return article_list

    # substract an id list from owner's already viewed articles id list
    def substract_viewed_articles(self, id_list):
        viewed_article_id_list = self.get_my_viewed_id_list()
        for viewed_id in viewed_article_id_list:
            if viewed_id in id_list:
                id_list[:] = (value for value in id_list if value != viewed_id)
        return id_list

    # Finds a random article, until the limit is reached
    # excludes viewed articles
    def get_random_article(self):
        viewed_article_id_list = self.get_my_viewed_id_list()
        while (len(self.article_list) < self.suggestion_limit):
            article = random.choice(Article.objects.all())
            if article.id in self.article_id_list:
                continue
            else:
                if article.id in viewed_article_id_list:
                    continue
                else:
                    self.article_list.append(article)

    def get_article_suggestionDTO_list(self):
        suggested_articles = self.get_article_suggestion()
        article_suggestionDTO_list = []
        for article in suggested_articles:
            if article:
                authors = Author.objects.filter(article=article)
                article_suggestionDTO_list.append(
                    ArticleSuggestionDTO(article.id, article.Title, article.PublicationDate, authors))
        return article_suggestionDTO_list
