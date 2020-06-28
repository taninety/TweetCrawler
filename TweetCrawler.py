import sys

from browserupproxy import Server
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import json
import re
import os
import requests

import time
import pytz
from datetime import datetime
from datetime import timezone


proxies = {"http": "Please input yourself", "https": "Please input yourself"}
browserupproxy_path = r'Please input yourself'
chromedriver_path = r'Please input yourself'
instagram_username = 'Please input yourself'
instagram_password = 'Please input yourself'
instagram_cookie_file = 'cookie_ig.json'


# start proxy and browser
server = Server(browserupproxy_path)
server.start()
proxy = server.create_proxy()

options = Options()
options.add_argument('--proxy-server={0}'.format(proxy.proxy))
options.add_argument('--ignore-certificate-errors')

driver = webdriver.Chrome(options=options, executable_path=chromedriver_path)


def getFileNameTwi(tweet, user):
    pytime = datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
    pyzone = pytime.replace(tzinfo=timezone.utc).astimezone(pytz.timezone('Asia/Tokyo'))
    fileName = pyzone.strftime('%Y%m%d_%H%M%S_JST') + '_twi[' + user['screen_name'] + '][' + tweet['id_str'] +']'
    return fileName

def downloadMediaTwi(tweet, file):
    if 'extended_entities' in tweet:
        if 'media' in tweet['extended_entities']:
            count = 1

            for media in tweet['extended_entities']['media']:
                if 'photo' in media['type']:
                    print('Downloading Photo...')
                    urlori = media['media_url']
                    ext = re.findall(r"media/.+\.(.+)$", urlori)[0]
                    urlpre = re.findall(r"(^.*media/.+)\..+$", urlori)[0]
                    url = urlpre + '?format=' + ext + '&name=orig'
                    print(url)

                if 'video' in media['type']:
                    print('Downloading Video...')
                    url = media['video_info']['variants'][0]['url']
                    maxbit = 0
                    for variant in media['video_info']['variants']:
                        if 'bitrate' in variant:
                            bitrate = variant['bitrate']
                        if maxbit < bitrate:
                            maxbit = bitrate
                            url = variant['url']
                    ext = 'mp4'

                r = requests.get(url, proxies=proxies)
                countName = '_' + str(count)
                with open(file + countName + '.' + ext , 'wb') as f:
                    f.write(r.content)
                count = count + 1

def getTwitter(base_url, folder):
    conver_id = re.findall(r"status/(.+?)$", base_url)[0]

    proxy.new_har(conver_id, options={'captureHeaders': True, 'captureContent': True, 'captureBinaryContent': True})
    driver.get(base_url)
    proxy.wait_for_traffic_to_stop(1000,6000)
    result = proxy.har

    for entry in result['log']['entries']:
        _url = entry['request']['url']
        method = entry['request']['method']

        if "/api.twitter.com/2/timeline/conversation" in _url and "GET" in method:
            _response = entry['response']
            _content = _response['content']['text']
            content = json.loads(_content)

            tweet = content['globalObjects']['tweets'][conver_id]
            user_id = tweet['user_id_str']
            user = content['globalObjects']['users'][user_id]
            output = {
                'tweet.' + conver_id : tweet,
                'user.' + user_id : user
            }
            filename = getFileNameTwi(tweet, user)
            downloadMediaTwi(tweet, folder + filename)

            if 'quoted_status_permalink' in tweet:
                queted = tweet['quoted_status_permalink']['expanded']
                queted_conver_id = re.findall(r"status/(.+?)$", queted)[0]
                queted_tweet = content['globalObjects']['tweets'][queted_conver_id]
                queted_user_id = queted_tweet['user_id_str']
                queted_user = content['globalObjects']['users'][queted_user_id]
                output['queted_tweet.' + queted_conver_id] = queted_tweet
                output['queted_user.' + queted_user_id] = queted_user
                downloadMediaTwi(queted_tweet, folder + filename + '_queted')

            count = 1
            reply_tweet = tweet
            while 'in_reply_to_status_id_str' in reply_tweet:
                reply_conver_id = reply_tweet['in_reply_to_status_id_str']
                reply_tweet = content['globalObjects']['tweets'][reply_conver_id]
                reply_user_id = reply_tweet['user_id_str']
                reply_user = content['globalObjects']['users'][reply_user_id]
                output['reply_tweet[' + str(count) + '].' + reply_conver_id] = reply_tweet
                output['reply_user[' + str(count) + '].' + reply_user_id] = reply_user
                downloadMediaTwi(reply_tweet, folder + filename + '_reply' + str(count))
                count = count + 1

            with open(folder + filename + '.json', 'w', encoding='utf8') as f:
                json.dump(output, f, ensure_ascii=False)

            break

def getFileNameIns(instagram):
    shortcode = instagram['shortcode']
    username = instagram['owner']['username']

    timestamp = instagram['taken_at_timestamp']
    pytime = datetime.utcfromtimestamp(timestamp)
    pyzone = pytime.replace(tzinfo=timezone.utc).astimezone(pytz.timezone('Asia/Tokyo'))
    timename = pyzone.strftime("%Y%m%d_%H%M%S_JST")

    filename = timename + '_ins[' + username + '][' + shortcode + ']'
    return filename

def downloadMediaIns(instagram, file):
    urls = []
    if 'edge_sidecar_to_children' not in instagram:
        if instagram['is_video'] == False:
            urls.append(instagram['display_url'])
        else:
            urls.append(instagram['video_url'])
    else:
        for edge in instagram['edge_sidecar_to_children']['edges']:
            if edge['node']['is_video'] == False:
                urls.append(edge['node']['display_url'])
            else:
                urls.append(edge['node']['video_url'])

    count = 1

    for url in urls:
        r = requests.get(url, proxies=proxies)

        countName = '_' + str(count)
        if 'jpg?' in url:
            print('Downloading Photo...')
            ext = 'jpg'
        else:
            print('Downloading Video...')
            ext = 'mp4'

        with open(file + countName + '.' + ext , 'wb') as f:
            f.write(r.content)
        count = count + 1

def getInstagram(base_url, folder):
    if not os.path.exists(instagram_cookie_file):
        driver.get('https://www.instagram.com/accounts/login/?source=auth_switcher')
        time.sleep(3)
        driver.find_element_by_name("username").send_keys(instagram_username)
        driver.find_element_by_name("password").send_keys(instagram_password)
        driver.find_element_by_name("password").send_keys(u'\ue007')
        time.sleep(3)

        cookies = driver.get_cookies()
        f = open(instagram_cookie_file, 'w')
        f.write(json.dumps(cookies))
        f.close()

    f = open(instagram_cookie_file)
    cookies = f.read()
    cookies = json.loads(cookies)
    f.close()

    c = {c['name']:c['value'] for c in cookies}
    r = requests.get(base_url + '?__a=1', cookies=c, proxies=proxies)

    output = json.loads(r.content)
    instagram = output['graphql']['shortcode_media']

    filename = getFileNameIns(instagram)
    downloadMediaIns(instagram, folder + filename)

    with open(folder + filename + '.json', 'w', encoding='utf8') as f:
        json.dump(output, f, ensure_ascii=False)

def exitSecure():
    # stop proxy and browser
    server.stop()
    driver.close()
    driver.quit()
    exit()


if (len(sys.argv) > 1):

    url = str(sys.argv[1])

    if url[0:4] != 'http':
        print("URL is wrong")
        exitSecure()

    foldername = 'temp'
    if not os.path.exists(foldername):
        os.makedirs(foldername)
        print('Created folder:' + foldername)

    print('Temp Downloading: ' + url)
    if 'twitter.com' in url:
        getTwitter(url, foldername + '/')
    if 'instagram.com' in url:
        getInstagram(url, foldername + '/')

else:
    #get urls file name : current month
    filelist = os.listdir('.')
    urls_file = ''
    for file in filelist:
        if '.urls' in file:
            urls_file = file
            print('Found input file: ' + file)
    if urls_file == '':
        print('Not Found input file' )
        exitSecure()

    #create folder
    foldername = urls_file[0:6]
    if not os.path.exists(foldername):
        os.makedirs(foldername)
        print('Created folder:' + foldername)
    filelist = os.listdir(foldername)
    filelist = list(filter(lambda x: 'json' in x, filelist))
    filestr = " ".join(filelist)

    #get urls
    lines = []
    for line in open(urls_file):
        if line[0:4] != 'http':
            continue
        line = line.strip('\n')
        findNumber = line.find(" ")
        if findNumber != -1:
            lines.append(line[0:findNumber])
        else:
            lines.append(line)

    if len(lines) != len(set(lines)):
        print('Urls have duplicates!')
        exitSecure()

    #begin download
    downloadNumber = 0
    for url in lines:
        if 'twitter.com' in url:
            conver_id = re.findall(r"status/(.+?)$", url)[0]
            if conver_id not in filestr:
                print('Downloading: ' + url)
                getTwitter(url, foldername + '/')
                downloadNumber = downloadNumber + 1
        if 'instagram.com' in url:
            conver_id = re.findall(r"com/p/(.+?)/*$", url)[0]
            if conver_id not in filestr:
                print('Downloading: ' + url)
                getInstagram(url, foldername + '/')
                downloadNumber = downloadNumber + 1

    print('Downloaded new item number: ' + str(downloadNumber))

exitSecure()