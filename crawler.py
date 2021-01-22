import asyncio
import concurrent.futures
import re
import logging

from copy import copy
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.parse import urlparse
from urllib.request import urlopen, Request


class IllegalArgumentError(ValueError):
	pass

class Crawler:

	# Variables
	output 	= None
	report 	= True

	exclude = []

	debug	= False

	urls_to_crawl = set([])
	url_strings_to_output = []
	crawled_or_crawling = set([])
	excluded = set([])

	marked = {}

	not_parseable_resources = (".docx", ".doc", ".7z", ".avi", ".mkv", ".mp4", ".jpg", ".jpeg", ".png", ".gif" ,".pdf", ".iso", ".rar", ".tar", ".tgz", ".zip", ".dmg", ".exe")

	linkregex = re.compile(b'<a [^>]*href=[\'|"](.*?)[\'"][^>]*?>')
	imageregex = re.compile (b'<img [^>]*src=[\'|"](.*?)[\'"].*?>')

	rp = None
	response_code={}
	nb_url=1
	nb_exclude=0

	domain = ""
	target_domain = ""
	scheme		  = ""

	def __init__(self, num_workers=1,domain=""):

		self.num_workers = num_workers

		self.domain 	= domain
		self.verbose    = True

		if self.debug:
			log_level = logging.DEBUG
		elif self.verbose:
			log_level = logging.INFO
		else:
			log_level = logging.ERROR

		logging.basicConfig(level=log_level, format='%(levelname)s - %(message)s')

		self.urls_to_crawl = {self.clean_link(domain)}
		self.url_strings_to_output = []
		self.num_crawled = 0

		if num_workers <= 0:
			raise IllegalArgumentError("Number or workers must be positive")

		try:
			url_parsed = urlparse(domain)
			self.target_domain = url_parsed.netloc
			self.scheme = url_parsed.scheme
		except:
			logging.error("Invalid domain")
			raise IllegalArgumentError("Invalid domain")


	def run(self):

		logging.info("Start the crawling process")

		if self.num_workers == 1:
			while len(self.urls_to_crawl) != 0:
				current_url = self.urls_to_crawl.pop()
				self.crawled_or_crawling.add(current_url)
				self.__crawl(current_url)
		else:
			event_loop = asyncio.get_event_loop()
			try:
				while len(self.urls_to_crawl) != 0:
					executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers)
					event_loop.run_until_complete(self.crawl_all_pending_urls(executor))
			finally:
				event_loop.close()

		logging.info("Crawling has reached end of all found links")


	async def crawl_all_pending_urls(self, executor):
		event_loop = asyncio.get_event_loop()

		crawl_tasks = []
		urls_to_crawl = copy(self.urls_to_crawl)
		self.urls_to_crawl.clear()
		for url in urls_to_crawl:
			self.crawled_or_crawling.add(url)
			task = event_loop.run_in_executor(executor, self.__crawl, url)
			crawl_tasks.append(task)

		await asyncio.wait(crawl_tasks)
		return



	def __crawl(self, current_url):
		url = urlparse(current_url)
		logging.info("Crawling #{}: {}".format(self.num_crawled, url.geturl()))
		self.num_crawled += 1

		request = Request(current_url)

		if not url.path.endswith(self.not_parseable_resources):
			try:
				response = urlopen(request)
			except Exception as e:
				if hasattr(e,'code'):
					if e.code in self.response_code:
						self.response_code[e.code]+=1
					else:
						self.response_code[e.code]=1

					if self.report:
						if e.code in self.marked:
							self.marked[e.code].append(current_url)
						else:
							self.marked[e.code] = [current_url]

				logging.debug ("{1} ==> {0}".format(e, current_url))
				return
		else:
			logging.debug("Ignore {0} content might be not parseable.".format(current_url))
			response = None

		# Read the response
		if response is not None:
			try:
				msg = response.read()
				if response.getcode() in self.response_code:
					self.response_code[response.getcode()]+=1
				else:
					self.response_code[response.getcode()]=1

				response.close()

			except Exception as e:
				logging.debug ("{1} ===> {0}".format(e, current_url))
				return
		else:
			msg = "".encode( )


		# Found links in html
		links = self.linkregex.findall(msg)
		for link in links:
			link = link.decode("utf-8", errors="ignore")
			logging.debug("Found : {0}".format(link))

			if link.startswith('/'):
				link = url.scheme + '://' + url[1] + link
			elif link.startswith('#'):
				link = url.scheme + '://' + url[1] + url[2] + link
			elif link.startswith(("mailto", "tel")):
				continue
			elif not link.startswith(('http', "https")):
				link = self.clean_link(urljoin(current_url, link))

			if "#" in link:
				link = link[:link.index('#')]


			# Parse the url to get domain and file extension
			parsed_link = urlparse(link)
			domain_link = parsed_link.netloc

			if link in self.crawled_or_crawling:
				continue
			if link in self.urls_to_crawl:
				continue
			if link in self.excluded:
				continue
			if domain_link != self.target_domain:
				continue
			if parsed_link.path in ["", "/"] and parsed_link.query == '':
				continue
			if "javascript" in link:
				continue
			if parsed_link.path.startswith("data:"):
				continue

			# Count one more URL
			self.nb_url+=1

			# Check if the current url doesn't contain an excluded word
			if not self.exclude_url(link):
				self.exclude_link(link)
				self.nb_exclude+=1
				continue

			logging.info("Links #{}: {}".format(self.num_crawled, link))

			self.urls_to_crawl.add(link)

	def clean_link(self, link):
		parts = list(urlsplit(link))
		parts[2] = self.resolve_url_path(parts[2])
		return urlunsplit(parts)

	def resolve_url_path(self, path):
		segments = path.split('/')
		segments = [segment + '/' for segment in segments[:-1]] + [segments[-1]]
		resolved = []
		for segment in segments:
			if segment in ('../', '..'):
				if resolved[1:]:
					resolved.pop()
			elif segment not in ('./', '.'):
				resolved.append(segment)
		return ''.join(resolved)


	def exclude_link(self,link):
		if link not in self.excluded:
			self.excluded.add(link)


	def exclude_url(self, link):
		for ex in self.exclude:
			if ex in link:
				return False
		return True

	def make_report(self):
		print ("Number of found URL : {0}".format(self.nb_url))
		print ("Number of links crawled : {0}".format(self.num_crawled))

		for code in self.marked:
			print ("Link with status {0}:".format(code))
			for uri in self.marked[code]:
				print ("\t- {0}".format(uri))