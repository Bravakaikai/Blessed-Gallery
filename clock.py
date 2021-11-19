from apscheduler.schedulers.blocking import BlockingScheduler
import os
import urllib.request
import datetime

sched = BlockingScheduler()

@sched.scheduled_job('cron', day_of_week='mon-fri', minute='*/20')
def scheduled_job():
    url = os.environ['HOME_URL']
    conn = urllib.request.urlopen(url)
        
    for key, value in conn.getheaders():
        print(key, value)

sched.start()