import hashlib
import json
import os
import re
import time
import sys
import requests
from bs4 import BeautifulSoup as BS


def getfilepathlist(path):  # 取得同一目录与子目录下所有视频文件的位置
    filelist = []
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            ext = ext[1:].lower()
            if ext in "mp4 flv f4v webm m4v mov 3gp 3g2 rm rmvb wmv avi asf mpg mpeg mpe ts div dv divx vob dat mkv swf lavf cpk dirac ram qt fli flc mod":
                filelist.append(os.path.join(dirpath, filename))
    return filelist


def getfilehash(videofullpath):
    with open(videofullpath, "rb") as fin:
        block = fin.read(16 * 1024 * 1024)  # type(block) = bytes
    md5 = hashlib.md5()
    md5.update(block)
    return md5.hexdigest()
    # 返回hash


def findtheanime(videofullpath):  # 调用dandanplay的匹配api，返回匹配结果
    fileHash = getfilehash(videofullpath)
    videoname = os.path.basename(videofullpath)
    headers = {"Accept": "application/json"}
    postjson = {
        "fileName": videoname,
        "fileHash": fileHash,
        "fileSize": 0,
        "videoDuration": 0,
        "matchMode": "hashAndFileName",
    }
    ddplayMatchResult = requests.post(
        url="https://api.acplay.net/api/v2/match", headers=headers, json=postjson)
    return ddplayMatchResult

def findtheanimewithouthash(videofullpath):  # 调用dandanplay的匹配api，返回匹配结果
    
    videoname = os.path.basename(videofullpath)
    headers = {"Accept": "application/json"}
    postjson = {
        "fileName": videoname,
        "fileHash": 12345678901234567890123456789012,
        "fileSize": 0,
        "videoDuration": 0,
        "matchMode": "fileNameOnly",
    }
    ddplayMatchResult = requests.post(
        url="https://api.acplay.net/api/v2/match", headers=headers, json=postjson)
    return ddplayMatchResult


def isMatched(ddplayMatchResult):  # 检查匹配结果是否精确
    if json.loads(ddplayMatchResult.text).get('isMatched'):
        return 1
    else:
        return 0


def findbangumiinfo(animeId):  # 调用dandanplay的查询番剧信息api，返回番剧查询结果

    bangumiresult = requests.get(
        'https://api.acplay.net/api/v2/bangumi/'+str(animeId))

    if bangumiresult.status_code == 200:
        # print('bangumiresult.text')
        return bangumiresult
    # else: print(bangumiresult.status_code)


def getmetadata(bangumiresult):  # 依据番剧查询结果返回番剧元数据dict

    bgmjson = json.loads(bangumiresult.text)
    metadatadict = {}
    for item in bgmjson['bangumi']['metadata']:
        key = item.split(':')[0].strip()
        value = item.split(':')[1].strip()
        metadatadict[key] = value
    # print('metadatadict')
    return metadatadict
    # 返回各种元数据dict


def changedate(str):  # 改变日期格式
    if r := re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', str):
        year = int(r.group(1))
        month = int(r.group(2))
        day = int(r.group(3))
        return '%04d-%02d-%02d' % (year, month, day)
    return ''


def getepdata(bangumiresult):  # 依据番剧查询结果返回单集元数据dict
    bgmjson = json.loads(bangumiresult.text)
    epdatadict = {}
    for item in bgmjson['bangumi']['episodes']:
        key = str(item['episodeId'])
        value = item
        epdatadict[key] = value
    # print(epdatadict)
    return epdatadict
    # 返回EP信息dict


def finishtvshownfo(bangumiresult):  # 完成番剧nfo
    metadatadict = getmetadata(bangumiresult)
    bgmjson = json.loads(bangumiresult.text)
    finalxml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
    <tvshow>
    <title>'''
    finalxml = finalxml+bgmjson['bangumi']['animeTitle']+'''</title>
    <originaltitle>'''
    headers = {
        'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)',
    }
    r = requests.get(bgmjson['bangumi']['bangumiUrl'], headers=headers)
    html = r.text
    soup = BS(html, 'html.parser')
    tags = soup.find_all('a', {'property': 'v:itemreviewed'})
    originaltitle = tags[0].text.encode('latin1').decode('utf8')
    finalxml = finalxml+originaltitle
    finalxml = finalxml+'''</originaltitle>
    <showtitle></showtitle>
    <sorttitle></sorttitle>
    <ratings>'''
    finalxml = finalxml+'''<rating name="Bangumi评分" max="10" default="true">
        <value>'''+str(bgmjson['bangumi']['ratingDetails']['Bangumi评分'])+'''</value>
        <votes></votes>
    </rating>'''
    finalxml = finalxml+'''</ratings>
    <userrating></userrating>
    <top250></top250>
    <season></season>
    <episode>'''+metadatadict.get('话数')+'''</episode>
    <displayseason></displayseason>
    <displayepisode></displayepisode>
    <outline></outline>
    <plot>'''+bgmjson['bangumi']['summary']+'''</plot>
    <tagline></tagline>
    <runtime>0</runtime><thumb aspect="poster">'''+bgmjson['bangumi']['imageUrl']+'''</thumb><fanart>
    </fanart>
    <mpaa></mpaa>
    <playcount>0</playcount>
    <lastplayed></lastplayed>'''
    if metadatadict.get('放送开始'):
        finalxml = finalxml+'<premiered>' + \
            changedate(metadatadict['放送开始'])+'</premiered>'
    elif metadatadict.get('上映年度'):
        finalxml = finalxml+'<premiered>' + \
            changedate(metadatadict['上映年度'])+'</premiered>'
    finalxml = finalxml+bgmjson['bangumi']['typeDescription']+'''<status></status>
    <code></code>
    <aired></aired>
    <studio>'''+metadatadict['动画制作']+'''</studio>
    <trailer></trailer>'''
    for bgmtage in bgmjson['bangumi']['tags']:
        finalxml = finalxml+'<tag>'+bgmtage['name']+'</tag>'

    # 这个xml似乎是不分顺序的，需要增加新的信息直接在此行添加
    finalxml = finalxml+'</tvshow>'
    return finalxml


def finishsinglepisodenfo(bangumiresult, singleepdata):  # 完成单集nfo
    metadatadict = getmetadata(bangumiresult)
    bgmjson = json.loads(bangumiresult.text)
    finalxml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
    <episodedetails>
    <title>'''+singleepdata['episodeTitle']+'</title><showtitle>'+bgmjson['bangumi']['animeTitle']+'</showtitle>'

    finalxml = finalxml+'''<ratings>
        <rating name="bangumi" max="10" default="true">
            <value>'''+str(bgmjson['bangumi']['rating'])+'''</value>
            <votes></votes>
        </rating>
    </ratings>'''
    finalxml = finalxml+'''<userrating></userrating>
    <plot></plot><playcount>0</playcount>
    <lastplayed></lastplayed><genre>TV动画</genre>'''
    if metadatadict.get('导演'):
        finalxml = finalxml+'<director>' + metadatadict['导演']+'</director>'
    elif metadatadict.get('总导演'):
        finalxml = finalxml+'<director>' + metadatadict['上映年度']+'</director>'

    finalxml = finalxml+'<premiered>' + \
        singleepdata['airDate'][0:10]+'''</premiered><studio>''' + \
        metadatadict['动画制作']+'</studio>'
    #finalxml=finalxml+ 这里填入演员代码
    # 这个xml似乎是不分顺序的，需要增加新的信息直接在此行添加
    finalxml = finalxml+'</episodedetails>'
    return finalxml


def is_int(s):  # 检查输入用
    try:
        int(s)
        return True
    except ValueError:
        pass

    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass

    return False


def resultselect(ddplayMatchResult, videofullpath):  # 完成匹配结果的人工选择，返回animeid
    counter = 0
    animeId = 0
    for everybangumi in json.loads(ddplayMatchResult.text)['matches']:
        counter = counter+1
        print(str(counter)+' '+everybangumi['animeTitle']+' ' +
              everybangumi['type']+' '+everybangumi['episodeTitle'])
    print(os.path.basename(videofullpath))
    # 展示每一个可能的选项和编号
    ordernumber = input('输入序号，0为以上均不准确')
    if is_int(ordernumber):
        ordernumber = int(ordernumber)
        if ordernumber == 0:
            animeId = 0
            print('以上均不准确，跳过')
            return animeId
        elif ordernumber >= 1 and ordernumber <= counter:
            animeId = json.loads(ddplayMatchResult.text)[
                'matches'][ordernumber-1]['animeId']
            return animeId
        else:
            animeId = 0
            print('输入错误，这个番剧跳过')
            return animeId
    else:
        animeId = 0
        print('输入错误，这个番剧跳过')
        return animeId


def finishbgmselect(ddplayMatchResult, videofullpath, selectflag, lastanimeId):# 一个拼接起来的函数，避免正文中复杂的判断条件
    animeIdAndEpisodeIdAndSelectFlag = [0, 0, 0]

    if isMatched(ddplayMatchResult) == 1:  # 先判断是否自动匹配
        ordernumber = 1
        animeIdAndEpisodeIdAndSelectFlag[0] = json.loads(ddplayMatchResult.text)[
            'matches'][0]['animeId']
        animeIdAndEpisodeIdAndSelectFlag[1] = json.loads(ddplayMatchResult.text)[
            'matches'][0]['episodeId']
        print('自动匹配'+videofullpath+"成功")
        return animeIdAndEpisodeIdAndSelectFlag

    elif selectflag == 0:  # 再判断是否手动选择
        animeIdAndEpisodeIdAndSelectFlag[0] = resultselect(
            ddplayMatchResult, videofullpath)
        if  animeIdAndEpisodeIdAndSelectFlag[0]!=0:
            for item in json.loads(ddplayMatchResult.text)['matches']:
                if item['animeId'] == animeIdAndEpisodeIdAndSelectFlag[0]:
                    animeIdAndEpisodeIdAndSelectFlag[1] = item['episodeId']
                
        a = input('是否进入自动模式,1为确认')
        if is_int(a):
            if int(a) == 1:
                animeIdAndEpisodeIdAndSelectFlag[2] = 1
        return animeIdAndEpisodeIdAndSelectFlag
    elif lastanimeId != 0:  # 是否进入自动跳过模式
        animeIdAndEpisodeIdAndSelectFlag[0] = lastanimeId
        for item in json.loads(ddplayMatchResult.text)['matches']:
            if item['animeId'] == lastanimeId:
                animeIdAndEpisodeIdAndSelectFlag[1] = item['episodeId']
                animeIdAndEpisodeIdAndSelectFlag[2] = selectflag
                print('使用上次选择匹配'+os.path.basename(videofullpath))
                return animeIdAndEpisodeIdAndSelectFlag
        print(os.path.basename(videofullpath)+'没能正确匹配')
        animeIdAndEpisodeIdAndSelectFlag = [lastanimeId, 0, selectflag]
        return animeIdAndEpisodeIdAndSelectFlag
    else:  # 进入自动跳过模式
        animeIdAndEpisodeIdAndSelectFlag = [lastanimeId, 0, selectflag]
        return animeIdAndEpisodeIdAndSelectFlag


# globalflag
lastvideoflag = 0
lastvideopath = 'lastvideopath'

selectflag = 0
lastanimeId = 0
episodeCounter = 0
totalEpisode = 0
finishBgmNfoFlag=0
# filelist=getfilepathlist(r'Z:\u2pt\[Hakugetsu&VCB-Studio]Gochuumon wa Usagi Desuka[1080p]\SPs')
filelist = getfilepathlist(os.path.dirname(sys.argv[0]))
for videofullpath in filelist:

    if lastvideoflag == 0:
        if os.path.exists(os.path.dirname(sys.argv[0])+r'\lastvideopath.txt'):
            with open(os.path.dirname(sys.argv[0])+r'\lastvideopath.txt', encoding='utf8') as lastvideopathtxt:
                if os.path.basename(videofullpath) == os.path.basename(lastvideopathtxt.readline()):
                    lastvideoflag = 1
                    lastvideopath = videofullpath
                    print('上次完成的文件是'+videofullpath+'\n'+'从上次完成的文件继续')
                    continue
                else:
                    continue
        else: lastvideoflag = 1
        
                    # 进行上次完成文件检测
    try:
        try:

            if os.path.dirname(videofullpath) != lastvideopath:
                selectflag = 0
                lastanimeId = 0
                episodeCounter = 0
                totalEpisode = 0
                finishBgmNfoFlag=0
                # 检测是否切换目录 重置flag

            ddplayMatchResult = findtheanime(videofullpath)
            animeIdAndEpisodeIdAndSelectFlag = finishbgmselect(
                ddplayMatchResult, videofullpath, selectflag, lastanimeId)

            if animeIdAndEpisodeIdAndSelectFlag[0] != 0:
                bangumiresult = findbangumiinfo(
                    animeIdAndEpisodeIdAndSelectFlag[0])
                epdatadict = getepdata(bangumiresult)
                if os.path.dirname(videofullpath) != lastvideopath or finishBgmNfoFlag==0:
                    tvshowdir = os.path.dirname(videofullpath)+r'\tvshow.nfo'
                    file = open(tvshowdir, "w", encoding="utf8")
                    file.write(finishtvshownfo(bangumiresult))
                    file.close()
                    # 完成番剧nfo写入
                    for item in json.loads(bangumiresult.text)['bangumi']['episodes']:
                        totalEpisode = totalEpisode+1
                    # 每个文件夹第一次进行总集数计算
                    finishBgmNfoFlag=1
                if animeIdAndEpisodeIdAndSelectFlag[1] != 0:
                    singleepdir = os.path.splitext(videofullpath)[0]+'.nfo'
                    file = open(singleepdir, 'w', encoding="utf8")
                    file.write(finishsinglepisodenfo(
                        bangumiresult, epdatadict[str(animeIdAndEpisodeIdAndSelectFlag[1])]))
                    file.close()
                    # 完成单集nfo写入
                print('完成'+videofullpath)
                time.sleep(1)

            else:
                print('跳过'+videofullpath)
            # 完成一集的写入

            file = open(os.path.dirname(
                sys.argv[0])+r'\lastvideopath.txt', 'w', encoding="utf8")
            file.write(videofullpath)
            file.close()
            lastvideopath = os.path.dirname(videofullpath)
            lastanimeId = animeIdAndEpisodeIdAndSelectFlag[0]
            selectflag = animeIdAndEpisodeIdAndSelectFlag[2]
            episodeCounter = episodeCounter+1
            
            # 收尾阶段 改变各种flag与计数器
            if animeIdAndEpisodeIdAndSelectFlag[0] != 0 and episodeCounter >= totalEpisode:
                selectflag = 0
                # 达到总集数上限时重置自动模式，防止错误选择

        except:
            print('自动模式出错，手动选择这一集')
            selectflag = 0
            lastanimeId = 0
            # 重置选择flag

            if os.path.dirname(videofullpath) != lastvideopath:
                selectflag = 0
                lastanimeId = 0
                episodeCounter = 0
                totalEpisode = 0
                finishBgmNfoFlag=0
                # 检测是否切换目录 重置flag

            ddplayMatchResult = findtheanimewithouthash(videofullpath)
            animeIdAndEpisodeIdAndSelectFlag = finishbgmselect(
                ddplayMatchResult, videofullpath, selectflag, lastanimeId)

            if animeIdAndEpisodeIdAndSelectFlag[0] != 0:
                bangumiresult = findbangumiinfo(
                    animeIdAndEpisodeIdAndSelectFlag[0])
                epdatadict = getepdata(bangumiresult)
                if os.path.dirname(videofullpath) != lastvideopath or finishBgmNfoFlag==0:
                    tvshowdir = os.path.dirname(videofullpath)+r'\tvshow.nfo'
                    file = open(tvshowdir, "w", encoding="utf8")
                    file.write(finishtvshownfo(bangumiresult))
                    file.close()
                    # 完成番剧nfo写入
                    for item in json.loads(bangumiresult.text)['bangumi']['episodes']:
                        totalEpisode = totalEpisode+1
                    # 每个文件夹第一次进行总集数计算
                    finishBgmNfoFlag=1
                if animeIdAndEpisodeIdAndSelectFlag[1] != 0:
                    singleepdir = os.path.splitext(videofullpath)[0]+'.nfo'
                    file = open(singleepdir, 'w', encoding="utf8")
                    file.write(finishsinglepisodenfo(
                        bangumiresult, epdatadict[str(animeIdAndEpisodeIdAndSelectFlag[1])]))
                    file.close()
                    # 完成单集nfo写入
                print('完成'+videofullpath)
                time.sleep(1)

            else:
                print('跳过'+videofullpath)
            # 完成一集的写入

            file = open(os.path.dirname(
                sys.argv[0])+r'\lastvideopath.txt', 'w', encoding="utf8")
            file.write(videofullpath)
            file.close()
            lastvideopath = os.path.dirname(videofullpath)
            lastanimeId = animeIdAndEpisodeIdAndSelectFlag[0]
            selectflag = animeIdAndEpisodeIdAndSelectFlag[2]
            episodeCounter = episodeCounter+1
            # 收尾阶段 改变各种flag与计数器
            if animeIdAndEpisodeIdAndSelectFlag[0] != 0 and episodeCounter >= totalEpisode:
                selectflag = 0
                # 达到总集数上限时重置自动模式，防止错误选择
    except:
        print('奇怪的问题，跳过这一集')
        file = open(os.path.dirname(
                sys.argv[0])+r'\lastvideopath.txt', 'w', encoding="utf8")
        file.write(videofullpath)
        file.close()
        lastvideopath = os.path.dirname(videofullpath)
        episodeCounter = episodeCounter+1
    

input('全部完成')


# path='D:\True Tears (2008) [Doki][1280x720 Hi10P BD FLAC]\[Doki] True Tears - 01 (1280x720 Hi10P BD FLAC) [2ABE42F9].mkv'
# bangumiresult=findbangumiinfo(findtheanime(path))
# singleepdata=getepdata(bangumiresult)['43250001']
# print(finishsinglepisodenfo(bangumiresult,singleepdata))
