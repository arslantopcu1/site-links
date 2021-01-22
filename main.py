#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import crawler

parser = argparse.ArgumentParser(description='Site crawler')
parser.add_argument('-w', '--worker', type=int, default=1, help="Number of workers if multithreading")
parser.add_argument('-d', '--domain',  default="http://blog.lesite.us", help="Domain ")

arg = parser.parse_args()

crawl = crawler.Crawler(domain=arg.domain, num_workers=arg.worker)
crawl.run()
crawl.make_report()