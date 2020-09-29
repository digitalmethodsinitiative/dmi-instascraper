import instaloader
import threading
import re
import wx


class ScraperMessage(wx.PyEvent):
    """
    Message to be passed to the main GUI
    """
    def __init__(self, id, data):
        """
        Instantiate new message

        :param id:  Message ID - determined by GUI and passed on to scraper
        :param data:  Data to send
        """
        wx.PyEvent.__init__(self)
        self.SetEventType(id)
        self.data = data


class InstagramScraper(threading.Thread):
    """
    Instagram scraper class

    Based on instaloader. Calls the requisite instaloader methods as required
    by scrape parameters and collects posts in memory. At the end, the posts
    are returned. While scraping, status and progress updates are passed to the
    GUI so the user can stay on top of what's happening.
    """
    interrupted = False
    results = None

    def __init__(self, event_id, parent, queries, max_posts, scrape_comments, scrape_files, scrape_target):
        """
        Instantiate scraper

        There are quite a few parameters and since we're running in a thread
        these cannot be passed to the run() method directly. So instead save
        them as object properties so they can be used later.

        :param event_id:  Event ID to use for messages to the GUI
        :param parent:  GUI handler (window) to send messages to
        :param list queries:  List of queries, #hashtags or @users
        :param int max_posts:  Posts to scrape per query
        :param bool scrape_comments:  Also scrape comments and save in CSV?
        :param bool scrape_files:  Also save metadata & files for each post?
        :param Path scrape_target:  Where to save scraped files
        """
        super().__init__()
        self.event_id = event_id
        self.parent = parent
        self.queries = queries
        self.max_posts = max_posts
        self.scrape_comments = scrape_comments
        self.scrape_files = scrape_files
        self.scrape_target = scrape_target

    def update_status(self, message):
        """
        Send a signal with a status update

        :param message:  Message to send to logger
        """
        wx.PostEvent(self.parent, ScraperMessage(self.event_id, {"type": "log", "value": message}))

    def update_progress(self, current, total):
        """
        Send a signal with a progress update

        Progress is calculated via the given parameters

        :param current:  Current amount of processed items
        :param total:  Total amount of items to process
        """
        wx.PostEvent(self.parent, ScraperMessage(self.event_id, {"type": "progress",
                                                                 "value": 100.0 * (float(current) / float(total))}))

    @staticmethod
    def instaloaderError(parent, event_id):
        """
        Intercept Instaloader error

        Instaloader logs its errors to stderr. But we need to handle them in the
        code here - so instaloader is monkey patched to override its error
        logger and if it's the type of error we're interested in we pass it on to
        the GUI for logging.

        :param parent:  Parent window to send message to
        :param event_id:  Event ID of the message to send
        """
        def wrapped_instaloaderError(context, msg, *args, **kwargs):
            limited = re.findall(r"The request will be retried in ([0-9]+) seconds, at ([0-9:]+).", msg)
            if limited:
                seconds, next_attempt = limited[0]
                wx.PostEvent(parent, ScraperMessage(event_id, {"type": "log",
                                                               "value": "Uh oh, Instagram noticed us! Waiting until %s before continuing..." % next_attempt}))

        return wrapped_instaloaderError

    def run(self):
        """
        Run scraper in thread

        This in turn calls another function, because that way we can catch
        exceptions in the scrape and clean them up as needed.
        """
        try:
            self.scrape()
        except RuntimeError as e:
            wx.PostEvent(self.parent, ScraperMessage(self.event_id, {"type": "status", "value": "INTERRUPTED"}))
            return

    def scrape(self):
        """
        Fetches data from Instagram via instaloader
        """
        # this is useful to include in the results because researchers are
        # always thirsty for them hashtags
        hashtag = re.compile(r"#([^\s,.+=-]+)")
        mention = re.compile(r"@([a-zA-Z0-9_]+)")

        # monkey patch the error handler because it prints to stderr and we
        # want to handle the error in python instead
        instaloader.instaloadercontext.InstaloaderContext.error = self.instaloaderError(self.parent, self.event_id)

        # instantiate instaloader
        instagram = instaloader.Instaloader(
            quiet=True,
            download_pictures=self.scrape_files,
            download_videos=self.scrape_files,
            download_comments=self.scrape_comments,
            download_geotags=False,
            download_video_thumbnails=False,
            compress_json=False,
            save_metadata=self.scrape_files
        )

        # ready our parameters
        queries = [query.strip() for query in self.queries]
        posts = []

        # for each query, get items
        for query in queries:
            chunk_size = 0
            self.update_status("Retrieving posts ('%s')" % query)
            try:
                if query[0] == "@":
                    query = query.replace("@", "")
                    profile = instaloader.Profile.from_username(instagram.context, query)
                    chunk = profile.get_posts()
                else:
                    query = query.replace("#", "")
                    chunk = instagram.get_hashtag_posts(query)

                # "chunk" is a generator so actually retrieve the posts next
                posts_processed = 0
                for post in chunk:
                    if self.interrupted:
                        raise RuntimeError("Interrupted while fetching posts from Instagram")

                    chunk_size += 1
                    self.update_status("Retrieving post list ('%s', %i posts)" % (query, chunk_size))
                    if posts_processed >= self.max_posts:
                        break
                    try:
                        posts.append(chunk.__next__())
                        posts[-1].query = query
                        posts_processed += 1
                    except StopIteration:
                        break

            except instaloader.InstaloaderException as e:
                # should we abort here and return 0 posts?
                self.update_status("Error while retrieving posts for query '%s'" % query)

        # go through posts, and retrieve comments
        results = []
        posts_processed = 0
        comments_bit = " and comments" if self.scrape_comments else ""

        for post in posts:
            if self.interrupted:
                raise RuntimeError("Interrupted while fetching post metadata from Instagram")

            posts_processed += 1
            self.update_status(
                "Downloading post%s %s, %i/%i" % (comments_bit, post.shortcode, posts_processed, len(posts)))
            self.update_progress(posts_processed, len(posts))

            thread_id = post.shortcode

            try:
                results.append({
                    "id": thread_id,
                    "thread_id": thread_id,
                    "parent_id": thread_id,
                    "body": post.caption if post.caption is not None else "",
                    "author": post.owner_username,
                    "timestamp": int(post.date_utc.timestamp()),
                    "type": "video" if post.is_video else "picture",
                    "url": post.video_url if post.is_video else post.url,
                    "thumbnail_url": post.url,
                    "hashtags": ",".join(post.caption_hashtags),
                    "usertags": ",".join(post.tagged_users),
                    "mentioned": ",".join(mention.findall(post.caption) if post.caption else ""),
                    "num_likes": post.likes,
                    "num_comments": post.comments,
                    "subject": ""
                })
            except (KeyError, instaloader.QueryReturnedNotFoundException, instaloader.ConnectionException):
                pass

            if self.scrape_files:
                instagram.download_post(post, self.scrape_target.joinpath(post.query).joinpath(post.shortcode))

            if not self.scrape_comments:
                continue

            try:
                for comment in post.get_comments():
                    answers = [answer for answer in comment.answers]

                    try:
                        results.append({
                            "id": comment.id,
                            "thread_id": thread_id,
                            "parent_id": thread_id,
                            "body": comment.text,
                            "author": comment.owner.username,
                            "timestamp": int(comment.created_at_utc.timestamp()),
                            "type": "comment",
                            "url": "",
                            "hashtags": ",".join(hashtag.findall(comment.text)),
                            "usertags": "",
                            "mentioned": ",".join(mention.findall(comment.text)),
                            "num_likes": comment.likes_count if hasattr(comment, "likes_count") else 0,
                            "num_comments": len(answers),
                            "subject": ""
                        })
                    except (KeyError, instaloader.QueryReturnedNotFoundException, instaloader.ConnectionException):
                        pass

                    # instagram only has one reply depth level at the time of
                    # writing, represented here
                    for answer in answers:
                        try:
                            results.append({
                                "id": answer.id,
                                "thread_id": thread_id,
                                "parent_id": comment.id,
                                "body": answer.text,
                                "author": answer.owner.username,
                                "timestamp": int(answer.created_at_utc.timestamp()),
                                "type": "comment",
                                "url": "",
                                "hashtags": ",".join(hashtag.findall(answer.text)),
                                "usertags": "",
                                "mentioned": ",".join(mention.findall(answer.text)),
                                "num_likes": answer.likes_count if hasattr(answer, "likes_count") else 0,
                                "num_comments": 0,
                                "subject": ""
                            })
                        except (KeyError, instaloader.QueryReturnedNotFoundException, instaloader.ConnectionException):
                            pass

            except (instaloader.QueryReturnedNotFoundException, instaloader.ConnectionException):
                # data not available...? this happens sometimes, not clear why
                pass

        # remove temporary fetched data and return posts
        wx.PostEvent(self.parent, ScraperMessage(self.event_id, {"type": "status", "value": "DONE"}))
        self.results = results
        return results
