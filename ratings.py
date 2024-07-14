import requests
import base64
import json
import math
import logging
import time


requests.adapters.DEFAULT_RETRIES = 5

logging.basicConfig(level = logging.DEBUG, format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_win_rate(rating1, rating2):
    """计算两个选手的胜率"""
    return 1.0 / (1 + 10 ** ((rating2 - rating1) / 400.0))

def get_seed(name, rating, ratings):
    """计算选手的预测排名"""
    seed = 1
    for j, j_rating in ratings.items():
        if name != j:
            seed += get_win_rate(j_rating[-1]['rating'], rating)

    return seed

def get_delta(name, rating, seed, rank):
    """计算选手的评分变化量"""
    m = math.sqrt(seed * rank)
    l, r = 100, 4000
    while l <= r:
        mid = (l + r) // 2
        if get_seed(name, mid, ratings) >= m:
            l = mid + 1
        else:
            r = mid - 1

    return (r - rating) / 2

def get_inc_1(deltas):
    """计算所有选手的平均增量"""
    sum_deltas = sum(deltas.values())
    return (-1 - sum_deltas) / len(deltas)

def get_inc_2(deltas):
    """计算前几名选手的平均增量"""
    sorted_deltas = sorted(deltas.items(), key=lambda x: x[1], reverse=True)
    num = min(4 * round(math.sqrt(len(deltas))), len(deltas))
    sum_deltas = sum(v for _, v in sorted_deltas[:num])
    return min(max(-sum_deltas / num, -10), 0)

def login():
    """登录到竞赛网站"""
    with open('account.json', 'r', encoding='utf-8') as f: 
        account = json.load(f)

    data = {
        'username': account['username'],
        'password': base64.b64decode(account['password']).decode("utf-8")
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    url = 'https://gmoj.net/senior/index.php/main/login'
    session = requests.Session()
    session.post(url, headers=headers, data=data)
    session.keep_alive = False # 关闭多余连接
    return session

def get_ratings(session, cid, ratings):
    """获取比赛的评分数据"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    response = session.get('https://gmoj.net/senior/index.php/contest/home/' + str(cid), headers=headers)
    if "Invalid contest!" in response.text:
        response.close()
        return -1
    if "Ended" not in response.text:
        response.close()
        return -2

    response.close()
    
    response = session.get('https://gmoj.net/senior/index.php/apicontest/standing/' + str(cid), headers=headers)
    status = response.status_code

    if status != 200:
        response.close()
        return ratings

    data = response.json()
    
    left, right = 0, 4000

    if "A" in data['contestInfo']['title']:
        left, right = 0, 1900
    elif "B" in data['contestInfo']['title']:
        left, right = 0, 1800
    elif "C" in data['contestInfo']['title']:
        left, right = 0, 1700

    rank = {}
    for i in data['data']:
        if i['name'] in ratings:
            if ratings[i['name']][-1]['rating'] < left or ratings[i['name']][-1]['rating'] > right:
                continue
        rank[i['name']] = i['rank']
        if i['name'] not in ratings:
            rating = 1500
            if "NOI" in data['contestInfo']['title']:
                rating = 2400
            elif "省选" in data['contestInfo']['title']:
                rating = 2200
            elif "A" in data['contestInfo']['title']:
                rating = 1800
            elif "B" in data['contestInfo']['title']:
                rating = 1700
            elif "C" in data['contestInfo']['title']:
                rating = 1500
            ratings[i['name']] = [{'rating': rating, 'cid': 0}]

    if(len(rank) == 0):
        return ratings

    seeds = {i: get_seed(i, ratings[i][-1]['rating'], ratings) for i in rank}
    deltas = {i: get_delta(i, ratings[i][-1]['rating'], seeds[i], rank[i]) for i in rank}

    inc1 = get_inc_1(deltas)
    for i in deltas:
        deltas[i] += inc1

    inc2 = get_inc_2(deltas)
    for i in deltas:
        deltas[i] += inc2

    for i in deltas:
        ratings[i].append({'rating': ratings[i][-1]['rating'] + deltas[i], 'cid': cid})

    response.close()
    return ratings

logging.info("Login...")

session = login()

logging.info("Get ratings...")

try:
    with open('ratings.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except:
    data = {'last_cid': 4060, 'ratings': {}, 'no_ended_contests': []}

ratings = data['ratings']
last_cid = data['last_cid']
no_ended_contests = data['no_ended_contests']

logging.info("Handle unended contests...")

# 处理未结束的比赛
for cid in no_ended_contests.copy():
    logging.info("Handle contest " + str(cid) + "...")
    res = get_ratings(session, cid, ratings)
    if res not in [-1, -2]:
        logging.info("Contest " + str(cid) + " ended.")
        no_ended_contests.remove(cid)
        ratings = res

data['no_ended_contests'] = no_ended_contests

logging.info("Handle new contests...")

# 处理新的比赛
while True:
    time.sleep(1)
    logging.info("Handle new contest " + str(last_cid) + "...")
    last_cid += 1
    res = get_ratings(session, last_cid, ratings)
    if res == -1:
        logging.info("Contest " + str(last_cid) + " not found.")
        last_cid -= 1
        break
    elif res == -2:
        logging.info("Contest " + str(last_cid) + " not ended yet.")
        no_ended_contests.append(last_cid)
    else:
        logging.info("Contest " + str(last_cid) + " ended.")
        ratings = res

data['last_cid'] = last_cid

 
logging.info("Sort ratings...")

ratings = dict(sorted(ratings.items(), key=lambda x: x[1][-1]['rating'], reverse=True))
data['ratings'] = ratings


logging.info("Save ratings...")

with open("ratings.json", 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False)