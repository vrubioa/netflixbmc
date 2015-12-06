#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import time
import shutil
import threading
import subprocess
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs
from resources.lib import chrome_cookies

trace_on = False
addon = xbmcaddon.Addon()

if addon.getSetting("sslEnable") == "true":
    try:
        # Add support for newer SSL connections in requests
        # Ensure OpenSSL is installed with system package manager on linux
        import resources
        sys.path.append(os.path.dirname(resources.lib.__file__))
        import resources.lib.pyOpenSSL
        import OpenSSL
        # https://urllib3.readthedocs.org/en/latest/security.html#openssl-pyopenssl
        import requests.packages.urllib3.contrib.pyopenssl
        requests.packages.urllib3.contrib.pyopenssl.inject_into_urllib3()
        verify_ssl = True
    except Exception as ex:
        import traceback
        print traceback.format_exc()
        print "ERROR importing OpenSSL handler"
        verify_ssl = False

import requests
import HTMLParser
import urllib
import socket

if addon.getSetting("sslEnable") == "false":
    verify_ssl = False
    print "SSL is Disabled"
    #supress warnings
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    from requests.packages.urllib3.exceptions import InsecurePlatformWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

try:
    import cPickle as pickle
except ImportError:
    import pickle

socket.setdefaulttimeout(40)
pluginhandle = int(sys.argv[1])

while (addon.getSetting("username") == "" or addon.getSetting("password") == ""):
    addon.openSettings()

htmlParser = HTMLParser.HTMLParser()
addonID = addon.getAddonInfo('id')
osWin = xbmc.getCondVisibility('system.platform.windows')
osLinux = xbmc.getCondVisibility('system.platform.linux')
osOSX = xbmc.getCondVisibility('system.platform.osx')
osAndroid = xbmc.getCondVisibility('system.platform.android')
addonDir = xbmc.translatePath(addon.getAddonInfo('path'))
defaultFanart = os.path.join(addonDir ,'fanart.png')
addonUserDataFolder = xbmc.translatePath("special://profile/addon_data/"+addonID)
icon = xbmc.translatePath('special://home/addons/'+addonID+'/icon.png')
utilityPath = xbmc.translatePath('special://home/addons/'+addonID+'/resources/NetfliXBMC_Utility.exe')
sendKeysPath = xbmc.translatePath('special://home/addons/'+addonID+'/resources/NetfliXBMC_SendKeys.exe')
fakeVidPath = xbmc.translatePath('special://home/addons/'+addonID+'/resources/fakeVid.mp4')
downloadScript = xbmc.translatePath('special://home/addons/'+addonID+'/download.py')
browserScript = xbmc.translatePath('special://home/addons/'+addonID+'/browser.sh')
searchHistoryFolder = os.path.join(addonUserDataFolder, "history")
cacheFolder = os.path.join(addonUserDataFolder, "cache")
cacheFolderCoversTMDB = os.path.join(cacheFolder, "covers")
cacheFolderFanartTMDB = os.path.join(cacheFolder, "fanart")
libraryFolder = xbmc.translatePath(addon.getSetting("libraryPath"))
libraryFolderMovies = os.path.join(libraryFolder, "Movies")
libraryFolderTV = os.path.join(libraryFolder, "TV")
cookieFile = xbmc.translatePath("special://profile/addon_data/"+addonID+"/cookies")
sessionFile = xbmc.translatePath("special://profile/addon_data/"+addonID+"/session")
chromeUserDataFolder = os.path.join(addonUserDataFolder, "chrome-user-data")
dontUseKiosk = addon.getSetting("dontUseKiosk") == "true"
browseTvShows = addon.getSetting("browseTvShows") == "true"
singleProfile = addon.getSetting("singleProfile") == "true"
isKidsProfile = addon.getSetting('isKidsProfile') == 'true'
showProfiles = addon.getSetting("showProfiles") == "true"
forceView = addon.getSetting("forceView") == "true"
useUtility = addon.getSetting("useUtility") == "true"
useChromeProfile = addon.getSetting("useChromeProfile") == "true"
remoteControl = addon.getSetting("remoteControl") == "true"
updateDB = addon.getSetting("updateDB") == "true"
useTMDb = addon.getSetting("useTMDb") == "true"
username = addon.getSetting("username")
password = addon.getSetting("password")
viewIdVideos = addon.getSetting("viewIdVideos")
viewIdEpisodes = addon.getSetting("viewIdEpisodesNew")
viewIdActivity = addon.getSetting("viewIdActivity")
winBrowser = int(addon.getSetting("winBrowserNew"))
language = addon.getSetting("language")
auth = addon.getSetting("auth")
authMyList = addon.getSetting("authMyList")
linuxUseShellScript = addon.getSetting("linuxUseShellScript") == "true"
debug = addon.getSetting("debug") == "true"

country = addon.getSetting("country")
if len(country)==0 and len(language.split("-"))>1:
    country = language.split("-")[1]

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
import ssl

class SSLAdapter(HTTPAdapter):
    '''An HTTPS Transport Adapter that uses an arbitrary SSL version.'''
    def init_poolmanager(self, connections, maxsize, block=False):
        ssl_version = addon.getSetting("sslSetting")
        ssl_version = None if ssl_version == 'Auto' else ssl_version
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=ssl_version)

urlMain = "https://www.netflix.com"
session = None
def newSession():
    s = requests.Session()
    s.mount('https://', SSLAdapter())
    s.headers.update({
        'User-Agent': 'User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:21.0) Gecko/20130331 Firefox/21.0',
    })
    return s
session = newSession()

def unescape(s):
    return htmlParser.unescape(s)

def load(url, post = None):
    debug("URL: " + url)
    r = ""
    try:
        if post:
            r = session.post(url, data=post, verify=verify_ssl).text
        else:
            r = session.get(url, verify=verify_ssl).text
    except AttributeError:
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC Error: Cookies have been deleted. Please try again.,10000,'+icon+')')
        newSession()
        saveState()
        if post:
            r = session.post(url, data=post, verify=verify_ssl).text
        else:
            r = session.get(url, verify=verify_ssl).text
    return r.encode('utf-8')

def saveState():
    tempfile = sessionFile+".tmp"
    if xbmcvfs.exists(tempfile):
        xbmcvfs.delete(tempfile)
    ser = pickle.dumps(session)
    fh = xbmcvfs.File(tempfile, 'wb')
    fh.write(ser)
    fh.close()
    if xbmcvfs.exists(sessionFile):
        xbmcvfs.delete(sessionFile)
    xbmcvfs.rename(tempfile, sessionFile)

# Load cached data
if not os.path.isdir(addonUserDataFolder):
    os.mkdir(addonUserDataFolder)
if not os.path.isdir(cacheFolder):
    os.mkdir(cacheFolder)
if not os.path.isdir(cacheFolderCoversTMDB):
    os.mkdir(cacheFolderCoversTMDB)
if not os.path.isdir(cacheFolderFanartTMDB):
    os.mkdir(cacheFolderFanartTMDB)
if not os.path.isdir(libraryFolder):
    xbmcvfs.mkdir(libraryFolder)
if not os.path.isdir(libraryFolderMovies):
    xbmcvfs.mkdir(libraryFolderMovies)
if not os.path.isdir(libraryFolderTV):
    xbmcvfs.mkdir(libraryFolderTV)
if os.path.exists(sessionFile):
    fh = xbmcvfs.File(sessionFile, 'rb')
    content = fh.read()
    fh.close()
    session = pickle.loads(content)

if not addon.getSetting("html5MessageShown"):
    dialog = xbmcgui.Dialog()
    ok = dialog.ok('IMPORTANT!', 'NetfliXBMC >=1.3.0 only supports the new Netflix HTML5 User Interface! The only browsers working with HTML5 DRM playback for now are Chrome>=37 (Win/OSX/Linux) and IExplorer>=11 (Win8.1 only). Make sure you have the latest version installed and check your Netflix settings. Using Silverlight may still partially work, but its not supported anymore. The HTML5 Player is also much faster, supports 1080p and gives you a smoother playback (especially on Linux). See forum.xbmc.org for more info...')
    addon.setSetting("html5MessageShown", "true")


def index():
    if login():
        addDir(translation(30011), "", 'main', "", "movie")
        addDir(translation(30012), "", 'main', "", "tv")
        addDir(translation(30143), "", 'wiHome', "", "both")
        if not singleProfile:
            profileName = addon.getSetting("profileName")
            addDir(translation(30113) + ' - [COLOR blue]' + profileName + '[/COLOR]', "", 'profileDisplayUpdate', 'DefaultAddonService.png', type, contextEnable=False)
        xbmcplugin.endOfDirectory(pluginhandle)


def profileDisplayUpdate():
    menuPath =  xbmc.getInfoLabel('Container.FolderPath')
    if not showProfiles:
        addon.setSetting("profile", None)
        saveState()
    xbmc.executebuiltin('Container.Update('+menuPath+')')


def main(type):
    addDir(translation(30002), urlMain+"/MyList?leid=595&link=seeall", 'listVideos', "", type)
    addDir(translation(30010), "", 'listViewingActivity', "", type)
    addDir(translation(30003), urlMain+"/WiRecentAdditionsGallery?nRR=releaseDate&nRT=all&pn=1&np=1&actionMethod=json", 'listVideos', "", type)
    if type=="tv":
        addDir(translation(30005), urlMain+"/WiGenre?agid=83", 'listVideos', "", type)
        addDir(translation(30007), "", 'listTvGenres', "", type)
    else:
        addDir(translation(30007), "WiGenre", 'listGenres', "", type)
    addDir(translation(30008), "", 'search', "", type)
    xbmcplugin.endOfDirectory(pluginhandle)


def wiHome(type):
    content = load(urlMain+"/WiHome")
    match1 = re.compile('<div class="mrow(.+?)"><div class="hd clearfix"><h3> (.+?)</h3></div><div class="bd clearfix"><div class="slider triangleBtns " id="(.+?)"', re.DOTALL).findall(content)
    match2 = re.compile('class="hd clearfix"><h3><a href="(.+?)">(.+?)<', re.DOTALL).findall(content)
    for temp, title, sliderID in match1:
        if not "hide-completely" in temp:
            title = re.sub('<.(.+?)</.>', '', title)
            addDir(title.strip(), sliderID, 'listSliderVideos', "", type)
    for url, title in match2:
        if "WiAltGenre" in url or "WiSimilarsByViewType" in url or "WiRecentAdditionsGallery" in url:
            addDir(title.strip(), url, 'listVideos', "", type)
    xbmcplugin.endOfDirectory(pluginhandle)


def listVideos(url, type, runAsWidget=False):
    if not runAsWidget:
        pDialog = xbmcgui.DialogProgress()
        pDialog.create('NetfliXBMC', translation(30142)+"...")
        pDialog.update( 0, translation(30142)+"...")
    xbmcplugin.setContent(pluginhandle, "movies")
    content = load(url)
    #content = load(url) # Terrible... currently first call doesn't have the content, it requires two calls....
    if not 'id="page-LOGIN"' in content:
        if singleProfile and 'id="page-ProfilesGate"' in content:
            forceChooseProfile()
        else:
            if '<div id="queue"' in content:
                content = content[content.find('<div id="queue"'):]
            content = content.replace("\\t","").replace("\\n", "").replace("\\", "")
            match = None
            if not match: match = re.compile('<span id="dbs(.+?)_.+?alt=".+?"', re.DOTALL).findall(content)
            if not match: match = re.compile('<span class="title.*?"><a id="b(.+?)_', re.DOTALL).findall(content)
            #if not match: match = re.compile('<a href="http://dvd.netflix.com/WiPlayer\?movieid=(.+?)&', re.DOTALL).findall(content)
            #if not match: match = re.compile('<a class="playHover" href=".+?WiPlayer\?movieid=(.+?)&', re.DOTALL).findall(content)
            if not match: match = re.compile('"boxart":".+?","titleId":(.+?),', re.DOTALL).findall(content)
            if not match: match = re.compile('WiPlayer\?movieid=([0-9]+?)&', re.DOTALL).findall(content)
            if not match: match = re.compile('"summary":.*?"id":([0-9]+)', re.DOTALL).findall(content)
            if not match: match = re.compile('"boxarts":.*?"id":([0-9]+)', re.DOTALL).findall(content)
            i = 1
            for videoID in match:
                if int(videoID)>10000000:
                    if not runAsWidget:
                        pDialog.update(i*100/len(match), translation(30142)+"...")
                    listVideo(videoID, "", "", False, False, type)
                    i+=1
            match1 = re.compile('&pn=(.+?)&', re.DOTALL).findall(url)
            match2 = re.compile('&from=(.+?)&', re.DOTALL).findall(url)
            matchApiRoot = re.compile('"API_ROOT":"(.+?)"', re.DOTALL).findall(content)
            matchApiBase = re.compile('"API_BASE_URL":"(.+?)"', re.DOTALL).findall(content)
            matchIdentifier = re.compile('"BUILD_IDENTIFIER":"(.+?)"', re.DOTALL).findall(content)
            if "agid=" in url and matchApiRoot and matchApiBase and matchIdentifier:
                genreID = url[url.find("agid=")+5:]
                addDir(translation(30001), matchApiRoot[0]+matchApiBase[0]+"/"+matchIdentifier[0]+"/wigenre?genreId="+genreID+"&full=false&from=51&to=100&_retry=0", 'listVideos', "", type)
            elif match1:
                currentPage = match1[0]
                nextPage = str(int(currentPage)+1)
                addDir(translation(30001), url.replace("&pn="+currentPage+"&", "&pn="+nextPage+"&"), 'listVideos', "", type)
            elif match2:
                currentFrom = match2[0]
                nextFrom = str(int(currentFrom)+50)
                currentTo = str(int(currentFrom)+49)
                nextTo = str(int(currentFrom)+99)
                addDir(translation(30001), url.replace("&from="+currentFrom+"&", "&from="+nextFrom+"&").replace("&to="+currentTo+"&", "&to="+nextTo+"&"), 'listVideos', "", type)
            if forceView and not runAsWidget:
                xbmc.executebuiltin('Container.SetViewMode('+viewIdVideos+')')
        xbmcplugin.endOfDirectory(pluginhandle)
    else:
        deleteCookies()
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30127))+',15000,'+icon+')')


def listSliderVideos(sliderID, type, runAsWidget=False):
    if not runAsWidget:
        pDialog = xbmcgui.DialogProgress()
        pDialog.create('NetfliXBMC', translation(30142)+"...")
        pDialog.update( 0, translation(30142)+"...")
    xbmcplugin.setContent(pluginhandle, "movies")
    content = load(urlMain+"/WiHome")
    if not 'id="page-LOGIN"' in content:
        if singleProfile and 'id="page-ProfilesGate"' in content:
            forceChooseProfile()
        else:
            content = content.replace("\\t","").replace("\\n", "").replace("\\", "")
            contentMain = content
            content = content[content.find('id="'+sliderID+'"'):]
            content = content[:content.find('class="ft"')]
            match = re.compile('<span id="dbs(.+?)_', re.DOTALL).findall(content)
            i = 1
            for videoID in match:
                listVideo(videoID, "", "", False, False, type)
                i+=1
            spl = contentMain.split('"remainderHTML":')
            for i in range(1, len(spl), 1):
                entry = spl[i]
                entry = entry[:entry.find('"rowId":')]
                if '"domId":"'+sliderID+'"' in entry:
                    match = re.compile('<span id="dbs(.+?)_', re.DOTALL).findall(entry)
                    i = 1
                    for videoID in match:
                        if not runAsWidget:
                            pDialog.update(i*100/(len(match)+10), translation(30142)+"...")
                        listVideo(videoID, "", "", False, False, type)
                        i+=1
            if forceView and not runAsWidget:
                xbmc.executebuiltin('Container.SetViewMode('+viewIdVideos+')')
            xbmcplugin.endOfDirectory(pluginhandle)
    else:
        deleteCookies()
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30127))+',15000,'+icon+')')


def listSearchVideos(url, type, runAsWidget=False):
    if not runAsWidget:
        pDialog = xbmcgui.DialogProgress()
        pDialog.create('NetfliXBMC', translation(30142)+"...")
        pDialog.update( 0, translation(30142)+"...")
    xbmcplugin.setContent(pluginhandle, "movies")
    content = load(url)
    content = json.loads(content)
    i = 1
    if "galleryVideos" in content:
        for item in content["galleryVideos"]["items"]:
            if not runAsWidget:
                pDialog.update(i*100/len(content["galleryVideos"]["items"]), translation(30142)+"...")
            listVideo(str(item["id"]), "", "", False, False, type)
            i+=1
        if forceView and not runAsWidget:
            xbmc.executebuiltin('Container.SetViewMode('+viewIdVideos+')')
        xbmcplugin.endOfDirectory(pluginhandle)
    else:
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30146))+',5000,'+icon+')')

def clean_filename(n, chars=None):
    if isinstance(n, str):
        return (''.join(c for c in unicode(n, "utf-8") if c not in '/\\:?"*|<>')).strip(chars)
    elif isinstance(n, unicode):
        return (''.join(c for c in n if c not in '/\\:?"*|<>')).strip(chars)

def listVideo(videoID, title, thumbUrl, tvshowIsEpisode, hideMovies, type):
    videoDetails = getVideoInfo(videoID)
    match = re.compile('<span class="title.*?>(.+?)<', re.DOTALL).findall(videoDetails)
    if not title:
        title = match[0].strip()
    year = ""
    match = re.compile('<span class="year.*?>(.+?)<', re.DOTALL).findall(videoDetails)
    if match:
        year = match[0]
    if not thumbUrl:
        match = re.compile('src="(.+?)"', re.DOTALL).findall(videoDetails)
        thumbUrl = match[0].replace("/webp/","/images/").replace(".webp",".jpg")
    match = re.compile('<span class="mpaaRating.*?>(.+?)<', re.DOTALL).findall(videoDetails)
    mpaa = ""
    if match:
        mpaa = match[0].strip()
    match = re.compile('<span class="duration.*?>(.+?)<', re.DOTALL).findall(videoDetails)
    duration = ""
    if match:
        duration = match[0].lower()
    if duration.split(' ')[-1] in ["minutes", "minutos", "minuter", "minutter", "minuuttia", "minuten"]:
        videoType = "movie"
        videoTypeTemp = videoType
        duration = duration.split(" ")[0]
    else:
        videoTypeTemp = "tv"
        if tvshowIsEpisode:
            videoType = "episode"
            year = ""
        else:
            videoType = "tvshow"
        duration = ""
    if useTMDb:
        yearTemp = year
        titleTemp = title
        if " - " in titleTemp:
            titleTemp = titleTemp[titleTemp.find(" - ")+3:]
        if "-" in yearTemp:
            yearTemp = yearTemp.split("-")[0]
        filename = clean_filename(videoID)+".jpg"
        filenameNone = clean_filename(videoID)+".none"
        coverFile = os.path.join(cacheFolderCoversTMDB, filename)
        coverFileNone = os.path.join(cacheFolderCoversTMDB, filenameNone)
        if not os.path.exists(coverFile) and not os.path.exists(coverFileNone):
            debug("Downloading Cover art. videoType:"+videoTypeTemp+", videoID:" + videoID + ", title:"+titleTemp+", year:"+yearTemp)
            xbmc.executebuiltin('XBMC.RunScript('+downloadScript+', '+urllib.quote_plus(videoTypeTemp)+', '+urllib.quote_plus(videoID)+', '+urllib.quote_plus(titleTemp)+', '+urllib.quote_plus(yearTemp)+')')
    match = re.compile('src=".+?">.*?<.*?>(.+?)<', re.DOTALL).findall(videoDetails)
    desc = ""
    if match:
        descTemp = match[0].decode("utf-8", 'ignore')
        #replace all embedded unicode in unicode (Norwegian problem)
        descTemp = descTemp.replace('u2013', u'\u2013').replace('u2026', u'\u2026')
        desc = htmlParser.unescape(descTemp)
    match = re.compile('Director:</dt><dd>(.+?)<', re.DOTALL).findall(videoDetails)
    director = ""
    if match:
        director = match[0].strip()
    match = re.compile('<span class="genre.*?>(.+?)<', re.DOTALL).findall(videoDetails)
    genre = ""
    if match:
        genre = match[0]
    match = re.compile('<span class="rating">(.+?)<', re.DOTALL).findall(videoDetails)
    rating = ""
    if match:
        rating = match[0]
    title = htmlParser.unescape(title.decode("utf-8"))
    nextMode = "playVideoMain"
    if browseTvShows and videoType == "tvshow":
        nextMode = "listSeasons"
    added = False
    if "/MyList" in url and videoTypeTemp==type:
        addVideoDirR(title, videoID, nextMode, thumbUrl, videoType, desc, duration, year, mpaa, director, genre, rating)
        added = True
    elif videoType == "movie" and hideMovies:
        pass
    elif videoTypeTemp==type or type=="both":
        addVideoDir(title, videoID, nextMode, thumbUrl, videoType, desc, duration, year, mpaa, director, genre, rating)
        added = True
    return added


def listGenres(type, videoType):
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    if isKidsProfile:
        type = 'KidsAltGenre'
    content = load(urlMain+"/WiHome")
    match = re.compile('/'+type+'\\?agid=(.+?)">(.+?)<', re.DOTALL).findall(content)
    # A number of categories (especially in the Kids genres) have duplicate entires and a lot of whitespice; create a stripped unique set
    unique_match = set((k[0].strip(), k[1].strip()) for k in match)
    for genreID, title in unique_match:
        if not genreID=="83":
            if isKidsProfile:
                addDir(title, urlMain+"/"+type+"?agid="+genreID+"&pn=1&np=1&actionMethod=json", 'listVideos', "", videoType)
            else:
                addDir(title, urlMain+"/"+type+"?agid="+genreID, 'listVideos', "", videoType)
    xbmcplugin.endOfDirectory(pluginhandle)


def listTvGenres(videoType):
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)
    content = load(urlMain+"/WiGenre?agid=83")
    content = content[content.find('id="subGenres_menu"'):]
    content = content[:content.find('</div>')]
    match = re.compile('<li ><a href=".+?/WiGenre\\?agid=(.+?)&.+?"><span>(.+?)<', re.DOTALL).findall(content)
    for genreID, title in match:
        addDir(title, urlMain+"/WiGenre?agid="+genreID, 'listVideos', "", videoType)
    xbmcplugin.endOfDirectory(pluginhandle)


def listSeasons(seriesName, seriesID, thumb):
    content = getSeriesInfo(seriesID)
    content = json.loads(content)
    seasons = []
    #VicVic Code
    for item in content["video"]["seasons"]:
	if item["title"] not in seasons:
        	seasons.append(item["title"])
    #for item in content["episodes"]:
    #    if item[0]["season"] not in seasons:
    #        seasons.append(item[0]["season"])
    for season in seasons:
        addSeasonDir("Season "+str(season), str(season), 'listEpisodes', thumb, seriesName, seriesID)
    xbmcplugin.endOfDirectory(pluginhandle)


def listEpisodes(seriesID, season):
    xbmcplugin.setContent(pluginhandle, "episodes")
    content = getSeriesInfo(seriesID)
    content = json.loads(content)
    #VicVic Code
    for test in content["video"]["seasons"]:
        episodeSeason = str(test["title"])
	if episodeSeason == season:
        	for item in test["episodes"]:
                	episodeID = str(item["episodeId"])
                	episodeNr = str(item["seq"])
                	episodeTitle = (episodeNr + ".  " + item["title"]).encode('utf-8')
                	duration = item["runtime"]
                	bookmarkPosition = item["bookmark"]["offset"]
                	playcount=0
                	if (duration>0 and float(bookmarkPosition)/float(duration))>=0.9:
                    		playcount=1
                	desc = item["synopsis"].encode('utf-8')
                	try:
                    		thumb = item["stills"][0]["url"]
                	except:
                    		thumb = ""
               		addEpisodeDir(episodeTitle, episodeID, 'playVideoMain', thumb, desc, str(duration), season, episodeNr, seriesID, playcount)

#    for test in content["episodes"]:
#        for item in test:
#            episodeSeason = str(item["season"])
#            if episodeSeason == season:
#                episodeID = str(item["episodeId"])
#                episodeNr = str(item["episode"])
#                episodeTitle = (episodeNr + ".  " + item["title"]).encode('utf-8')
#                duration = item["runtime"]
#                bookmarkPosition = item["bookmarkPosition"]
#                playcount=0
#                if (duration>0 and float(bookmarkPosition)/float(duration))>=0.9:
#                    playcount=1
#                desc = item["synopsis"].encode('utf-8')
#                try:
#                    thumb = item["stills"][0]["url"]
#                except:
#                    thumb = ""
#                addEpisodeDir(episodeTitle, episodeID, 'playVideoMain', thumb, desc, str(duration), season, episodeNr, seriesID, playcount)
    if forceView:
        xbmc.executebuiltin('Container.SetViewMode('+viewIdEpisodes+')')
    xbmcplugin.endOfDirectory(pluginhandle)


def listViewingActivity(type, runAsWidget=False):
    if not runAsWidget:
        pDialog = xbmcgui.DialogProgress()
        pDialog.create('NetfliXBMC', translation(30142)+"...")
        pDialog.update( 0, translation(30142)+"...")
    xbmcplugin.setContent(pluginhandle, "movies")
    content = load(urlMain+"/WiViewingActivity")
    count = 0
    videoIDs = []
    spl = re.compile('(<li .*?data-series=.*?</li>)', re.DOTALL).findall(content)
    #spl = content.split('')
    for i in range(1, len(spl), 1):
        entry = spl[i]
        if not runAsWidget:
            pDialog.update((count+1)*100/len(spl), translation(30142)+"...")
        matchId = re.compile('data-movieid="(.*?)"', re.DOTALL).findall(entry)
        if matchId:
            videoID = matchId[0]
        match = re.compile('class="col date nowrap">(.+?)<', re.DOTALL).findall(entry)
        date = match[0]
        matchTitle1 = re.compile('class="seriestitle">(.+?)</a>', re.DOTALL).findall(entry)
        matchTitle2 = re.compile('class="col title">.+?>(.+?)<', re.DOTALL).findall(entry)
        if matchTitle1:
            title = htmlParser.unescape(matchTitle1[0].decode("utf-8")).replace("</span>", "").encode("utf-8")
        elif matchTitle2:
            title = matchTitle2[0]
        else:
            title = ""
        title = date+" - "+title
        if videoID not in videoIDs:
            videoIDs.append(videoID)
            # due to limitations in the netflix api, there is no way to get the seriesId of an
            # episode, so the 4 param is set to True to treat tv episodes the same as movies.
            added = listVideo(videoID, title, "", True, False, type)
            if added:
                count += 1
            if count == 40:
                break
    if forceView and not runAsWidget:
        xbmc.executebuiltin('Container.SetViewMode('+viewIdActivity+')')
    xbmcplugin.endOfDirectory(pluginhandle)


def getVideoInfo(videoID):
    cacheFile = os.path.join(cacheFolder, videoID+".cache")
    content = ""
    #if os.path.exists(cacheFile):
    #    fh = xbmcvfs.File(cacheFile, 'r')
    #    content = fh.read()
    #    fh.close()
    #if not content:
    print "URL Download %s/JSON/BOB?movieid=%s" % (urlMain,videoID)
    content = load(urlMain+"/JSON/BOB?movieid="+videoID)
    fh = xbmcvfs.File(cacheFile, 'w')
    fh.write(content)
    fh.close()
    return content.replace("\\t","").replace("\\n", "").replace("\\", "")


def getSeriesInfo(seriesID):
    cacheFile = os.path.join(cacheFolder, seriesID+"_episodes.cache")
    content = ""
    if os.path.exists(cacheFile) and (time.time()-os.path.getmtime(cacheFile) < 60*5):
        fh = xbmcvfs.File(cacheFile, 'r')
        content = fh.read()
        fh.close()
    if not content:
        url = "http://www.netflix.com/api/shakti/6db00e6b/metadata?movieid="+seriesID
	#url = "http://api-global.netflix.com/desktop/odp/episodes?languages="+language+"&forceEpisodes=true&routing=redirect&video="+seriesID+"&country="+country
	print "URL of Download %s" % url
	content = load(url)
        fh = xbmcvfs.File(cacheFile, 'w')
        fh.write(content)
        fh.close()

    # if netflix throws exception they may still return content after the exception
    index = content.find('{"title":')
    if index != -1:
        content = content[index:]

    return content


def addMyListToLibrary():

    if not singleProfile:
        token = ""
        if addon.getSetting("profile"):
            token = addon.getSetting("profile")
            load("https://www.netflix.com/SwitchProfile?tkn="+token)

    content = load(urlMain+"/MyList?leid=595&link=seeall")
    if not 'id="page-LOGIN"' in content:
        if singleProfile and 'id="page-ProfilesGate"' in content:
            forceChooseProfile()
        else:
            if '<div id="queue"' in content:
                content = content[content.find('<div id="queue"'):]
            content = content.replace("\\t","").replace("\\n", "").replace("\\", "")
            match1 = re.compile('<span id="dbs(.+?)_.+?alt=".+?"', re.DOTALL).findall(content)
            match2 = re.compile('<span class="title.*?"><a id="b(.+?)_', re.DOTALL).findall(content)
            match3 = re.compile('<a href="http://dvd.netflix.com/WiPlayer\?movieid=(.+?)&', re.DOTALL).findall(content)
            match4 = re.compile('<a class="playHover" href=".+?WiPlayer\?movieid=(.+?)&', re.DOTALL).findall(content)
            match5 = re.compile('"boxart":".+?","titleId":(.+?),', re.DOTALL).findall(content)
            if match1:
                match = match1
            elif match2:
                match = match2
            elif match3:
                match = match3
            elif match4:
                match = match4
            elif match5:
                match = match5
                
            for videoID in match:
                videoDetails = getVideoInfo(videoID)
                match = re.compile('<span class="title ".*?>(.+?)<\/span>', re.DOTALL).findall(videoDetails)
                title = match[0].strip()
                title = htmlParser.unescape(title.decode("utf-8"))
                match = re.compile('<span class="year".*?>(.+?)<\/span>', re.DOTALL).findall(videoDetails)
                year = ""
                if match:
                    year = match[0]
                match = re.compile('<span class="duration.*?".*?>(.+?)<\/span>', re.DOTALL).findall(videoDetails)
                duration = ""
                if match:
                    duration = match[0].lower()
                if "minutes" in duration:
                    try:
                        if year:
                            title = title+" ("+year+")"
                        addMovieToLibrary(videoID, title, False)
                    except:
                        pass
                else:
                    try:
                        addSeriesToLibrary(videoID, title, "", False)
                    except:
                        pass
            if updateDB:
                xbmc.executebuiltin('UpdateLibrary(video)')

def playVideo(id):
    listitem = xbmcgui.ListItem(path=fakeVidPath)
    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
    playVideoMain(id)
    xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()


def playVideoMain(id):
    xbmc.Player().stop()
    if singleProfile:
        url = urlMain+"/WiPlayer?movieid="+id
    else:
        token = ""
        if addon.getSetting("profile"):
            token = addon.getSetting("profile")
        #url = "https://www.netflix.com/SwitchProfile?tkn="+token+"&nextpage="+urllib.quote_plus(urlMain+"/WiPlayer?movieid="+id)
	url = "https://www.netflix.com/SwitchProfile?tkn="+token+"&nextpage="+urllib.quote_plus(urlMain+"/watch/"+id)
    if osOSX:
        launchChrome(url)
        #xbmc.executebuiltin("RunPlugin(plugin://plugin.program.chrome.launcher/?url="+urllib.quote_plus(url)+"&mode=showSite&kiosk="+kiosk+")")
        try:
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
            subprocess.Popen('cliclick kp:arrow-up', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
            subprocess.Popen('cliclick kp:arrow-up', shell=True)
            xbmc.sleep(5000)
            subprocess.Popen('cliclick c:500,500', shell=True)
            subprocess.Popen('cliclick kp:arrow-up', shell=True)
        except:
            pass
    elif osAndroid:
        xbmc.executebuiltin('XBMC.StartAndroidActivity("","android.intent.action.VIEW","","' + urlMain+'/watch/' + id + '")')
    elif osLinux:
        if linuxUseShellScript:
            xbmc.executebuiltin('LIRC.Stop')
            
            call = '"'+browserScript+'" "'+url+'"';
            debug("Browser Call: " + call)
            subprocess.call(call, shell=True)
            
            xbmc.executebuiltin('LIRC.Start')
        else:
	    print "URL Download %s" % url
            launchChrome(url)
            #xbmc.executebuiltin("RunPlugin(plugin://plugin.program.chrome.launcher/?url="+urllib.quote_plus(url)+"&mode=showSite&kiosk="+kiosk+")")
            try:
                xbmc.sleep(5000)
                subprocess.Popen('xdotool mousemove 9999 9999', shell=True)
                xbmc.sleep(5000)
                subprocess.Popen('xdotool mousemove 9999 9999', shell=True)
                xbmc.sleep(5000)
                subprocess.Popen('xdotool mousemove 9999 9999', shell=True)
            except:
                pass
    elif osWin:
        if winBrowser == 1:
            path = 'C:\\Program Files\\Internet Explorer\\iexplore.exe'
            path64 = 'C:\\Program Files (x86)\\Internet Explorer\\iexplore.exe'
            if os.path.exists(path):
                subprocess.Popen('"'+path+'" -k "'+url+'"', shell=False)
            elif os.path.exists(path64):
                subprocess.Popen('"'+path64+'" -k "'+url+'"', shell=False)
        else:
            launchChrome(url)
            #xbmc.executebuiltin("RunPlugin(plugin://plugin.program.chrome.launcher/?url="+urllib.quote_plus(url)+"&mode=showSite&kiosk="+kiosk+")")
        if useUtility:
            subprocess.Popen('"'+utilityPath+'"', shell=False)

    myWindow = window('window.xml', addon.getAddonInfo('path'), 'default',)
    myWindow.doModal()
    myWindow.stopWakeupThread() # insurance, in case self.close() wasn't the method by which the window was closed

def launchChrome(url):
    kiosk = "yes"
    if dontUseKiosk:
        kiosk = "no"

    profileFolder = ""
    if useChromeProfile:
        if not os.path.exists(chromeUserDataFolder):
            import zipfile
            zip = os.path.join(addonDir, "resources", "chrome-user-data.zip")
            with open(zip, "rb") as zf:
                z = zipfile.ZipFile(zf)
                z.extractall(addonUserDataFolder)
        profileFolder = "&profileFolder="+urllib.quote_plus(chromeUserDataFolder)

        # Inject cookies
        chrome_cookies.inject_cookies_into_chrome(session, os.path.join(chromeUserDataFolder, "Default", "Cookies"))


    xbmc.executebuiltin("RunPlugin(plugin://plugin.program.chrome.launcher/?url="+urllib.quote_plus(url)+"&mode=showSite&kiosk="+kiosk+profileFolder+")")

def configureUtility():
    if osWin:
        subprocess.Popen('"'+utilityPath+'"'+' config=yes', shell=False)

def chromePluginOptions():
    url = "chrome-extension://najegmllpphoobggcngjhcpknknljhkj/html/options.html"
    launchChrome(url)

def deleteCookies():
    if os.path.exists(cookieFile):
        os.remove(cookieFile)
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,Cookies have been deleted!,5000,'+icon+')')
    if os.path.exists(sessionFile):
        os.remove(sessionFile)
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,Session cookies have been deleted!,5000,'+icon+')')


def deleteCache():
    if os.path.exists(cacheFolder):
        try:
            shutil.rmtree(cacheFolder)
            xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,Cache has been deleted!,5000,'+icon+')')
        except:
            pass

def deleteChromeUserDataFolder():
    if os.path.exists(chromeUserDataFolder):
        try:
            shutil.rmtree(chromeUserDataFolder)
            xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,Chrome UserData has been deleted!,5000,'+icon+')')
        except:
            pass

def resetAddon():
    dialog = xbmcgui.Dialog()
    if dialog.yesno("NetfliXBMC:", "Really reset the addon?"):
      if os.path.exists(addonUserDataFolder):
          try:
              shutil.rmtree(addonUserDataFolder)
              xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,Addon has been reset!,5000,'+icon+')')
          except:
              pass

def search(type):
    keyboard = xbmc.Keyboard('', translation(30008))
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        search_string = keyboard.getText().replace(" ", "+")
        listSearchVideos("http://api-global.netflix.com/desktop/search/instantsearch?esn=www&term="+search_string+"&locale="+language+"&country="+country+"&authURL="+auth+"&_retry=0&routing=redirect", type)

def addToQueue(id):
    if authMyList:
        encodedAuth = urllib.urlencode({'authURL': authMyList})
        load(urlMain+"/AddToQueue?movieid="+id+"&qtype=INSTANT&"+encodedAuth)
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30144))+',3000,'+icon+')')
    else:
        debug("Attempted to addToQueue without valid authMyList")

def removeFromQueue(id):
    if authMyList:
        encodedAuth = urllib.urlencode({'authURL': authMyList})
        load(urlMain+"/QueueDelete?"+encodedAuth+"&qtype=ED&movieid="+id)
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30145))+',3000,'+icon+')')
        xbmc.executebuiltin("Container.Refresh")
    else:
         debug("Attempted to removeFromQueue without valid authMyList")


def displayLoginProgress(progressWindow, value, message):
    progressWindow.update( value, "", message, "" )
    if progressWindow.iscanceled():
        return False
    else:
        return True


def login():
    #setup login progress display
    loginProgress = xbmcgui.DialogProgress()
    loginProgress.create('NETFLIXBMC', str(translation(30216)) + '...')
    displayLoginProgress(loginProgress, 25, str(translation(30217)))

    session.cookies.clear()
    content = load(urlMain+"/Login")
    match = re.compile('"LOCALE":"(.+?)"', re.DOTALL|re.IGNORECASE).findall(content)
    if match and not addon.getSetting("language"):
        addon.setSetting("language", match[0])
    if not "Sorry, Netflix is not available in your country yet." in content and not "Sorry, Netflix hasn't come to this part of the world yet" in content:
        match = re.compile('id="signout".+?authURL=(.+?)"', re.DOTALL).findall(content)
        if match:
            addon.setSetting("auth", match[0])
        if 'id="page-LOGIN"' in content:
            match = re.compile('name="authURL" value="(.+?)"', re.DOTALL).findall(content)
            authUrl = match[0]
            addon.setSetting("auth", authUrl)
            #postdata = "authURL="+urllib.quote_plus(authUrl)+"&email="+urllib.quote_plus(username)+"&password="+urllib.quote_plus(password)+"&RememberMe=on"
            postdata ={ "authURL":authUrl,
                        "email":username,
                        "password":password,
                        "RememberMe":"on"
                        }
            #content = load("https://signup.netflix.com/Login", "authURL="+urllib.quote_plus(authUrl)+"&email="+urllib.quote_plus(username)+"&password="+urllib.quote_plus(password)+"&RememberMe=on")
            displayLoginProgress(loginProgress, 50, str(translation(30218)))
            content = load("https://signup.netflix.com/Login", postdata)
            if 'id="page-LOGIN"' in content:
                # Login Failed
                xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30127))+',15000,'+icon+')')
                return False
            match = re.compile('"LOCALE":"(.+?)"', re.DOTALL|re.IGNORECASE).findall(content)
            if match and not addon.getSetting("language"):
                addon.setSetting("language", match[0])
            match = re.compile('"COUNTRY":"(.+?)"', re.DOTALL|re.IGNORECASE).findall(content)
            if match:
                # always overwrite the country code, to cater for switching regions
                debug("Setting Country: " + match[0])
                addon.setSetting("country", match[0])
            saveState()
            displayLoginProgress(loginProgress, 75, str(translation(30219)))

        if not addon.getSetting("profile") and not singleProfile:
            chooseProfile()
        elif not singleProfile and showProfiles:
            chooseProfile()
        elif not singleProfile and not showProfiles:
            loadProfile()
        else:
            getMyListChangeAuthorisation()
        if loginProgress:
            if not displayLoginProgress(loginProgress, 100, str(translation(30220))):
                return False
            xbmc.sleep(500)
            loginProgress.close()
        return True
    else:
        xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30126))+',10000,'+icon+')')
        if loginProgress:
            loginProgress.close()
        return False

def debug(message):
    if debug:
        print message

def loadProfile():
    savedProfile = addon.getSetting("profile")
    if savedProfile:
        load("https://api-global.netflix.com/desktop/account/profiles/switch?switchProfileGuid="+savedProfile)
        saveState()
    else:
        debug("LoadProfile: No stored profile found")
    getMyListChangeAuthorisation()

def chooseProfile():
    content = load("https://www.netflix.com/ProfilesGate?nextpage=http%3A%2F%2Fwww.netflix.com%2FDefault")
    matchType = 0
    match = re.compile('"profileName":"(.+?)".+?token":"(.+?)"', re.DOTALL).findall(content)
    if len(match):
        matchType = 1
    if not len(match):
        match = re.compile('"firstName":"(.+?)".+?guid":"(.+?)".+?experience":"(.+?)"', re.DOTALL).findall(content)
        if len(match):
            matchType = 1
    if not len(match):
        match = re.compile('"experience":"(.+?)".+?guid":"(.+?)".+?profileName":"(.+?)"', re.DOTALL).findall(content)
        if len(match):
            matchType = 2
    profiles = []
    # remove any duplicated profile data found during page scrape
    match = [item for count, item in enumerate(match) if item not in match[:count]]

    if matchType == 1:
        for p, t, e in match:
            profile = {'name': unescape(p), 'token': t, 'isKids': e=='jfk'}
            profiles.append(profile)
    elif matchType == 2:
        for e, t, p in match:
            profile = {'name': unescape(p), 'token': t, 'isKids': e=='jfk'}
            profiles.append(profile)

    if matchType > 0:
        dialog = xbmcgui.Dialog()
        nr = dialog.select(translation(30113), [profile['name'] for profile in profiles])
        if nr >= 0:
            selectedProfile = profiles[nr]
        else:
            selectedProfile = profiles[0]
        load("https://api-global.netflix.com/desktop/account/profiles/switch?switchProfileGuid="+selectedProfile['token'])
        addon.setSetting("profile", selectedProfile['token'])
        addon.setSetting("isKidsProfile", 'true' if selectedProfile['isKids'] else 'false')
        addon.setSetting("profileName", selectedProfile['name'])
        saveState()
        getMyListChangeAuthorisation()
    else:
        debug("Netflixbmc::chooseProfile: No profiles were found")

def getMyListChangeAuthorisation():
    content = load(urlMain+"/WiHome")
    match = re.compile('"xsrf":"(.+?)"', re.DOTALL).findall(content)
    if match:
        authMyList = match[0]
        addon.setSetting("authMyList", match[0])

def forceChooseProfile():
    addon.setSetting("singleProfile", "false")
    xbmc.executebuiltin('XBMC.Notification(NetfliXBMC:,'+str(translation(30111))+',5000,'+icon+')')
    chooseProfile()


def addMovieToLibrary(movieID, title, singleUpdate=True):
    movieFolderName = clean_filename(title+".strm", ' .').strip(' .')
    dirAndFilename = os.path.join(libraryFolderMovies, movieFolderName)
    fh = xbmcvfs.File(dirAndFilename, 'w')
    fh.write("plugin://plugin.video.netflixbmc/?mode=playVideo&url="+movieID)
    fh.close()
    if updateDB and singleUpdate:
        xbmc.executebuiltin('UpdateLibrary(video)')


def addSeriesToLibrary(seriesID, seriesTitle, season, singleUpdate=True):
    seriesFolderName = clean_filename(seriesTitle, ' .')
    seriesDir = os.path.join(libraryFolderTV, seriesFolderName)
    if not os.path.isdir(seriesDir):
        xbmcvfs.mkdir(seriesDir)
    content = getSeriesInfo(seriesID)
    content = json.loads(content)
    for test in content["episodes"]:
        for item in test:
            episodeSeason = str(item["season"])
            seasonCheck = True
            if season:
                seasonCheck = episodeSeason == season
            if seasonCheck:
                seasonDir = os.path.join(seriesDir, "Season "+episodeSeason)
                if not os.path.isdir(seasonDir):
                    xbmcvfs.mkdir(seasonDir)
                episodeID = str(item["episodeId"])
                episodeNr = str(item["episode"])
                episodeTitle = item["title"].encode('utf-8')
                if len(episodeNr) == 1:
                    episodeNr = "0"+episodeNr
                seasonNr = episodeSeason
                if len(seasonNr) == 1:
                    seasonNr = "0"+seasonNr
                filename = "S"+seasonNr+"E"+episodeNr+" - "+episodeTitle+".strm"
                filename = clean_filename(filename, ' .')
                fh = xbmcvfs.File(os.path.join(seasonDir, filename), 'w')
                fh.write("plugin://plugin.video.netflixbmc/?mode=playVideo&url="+episodeID)
                fh.close()
    if updateDB and singleUpdate:
        xbmc.executebuiltin('UpdateLibrary(video)')


def playTrailer(title):
    try:
        content = load("http://gdata.youtube.com/feeds/api/videos?vq="+title.strip().replace(" ", "+")+"+trailer&racy=include&orderby=relevance")
        match = re.compile('<id>http://gdata.youtube.com/feeds/api/videos/(.+?)</id>', re.DOTALL).findall(content.split('<entry>')[2])
        xbmc.Player().play("plugin://plugin.video.youtube/play/?video_id=" + match[0])
    except:
        pass


def translation(id):
    return addon.getLocalizedString(id).encode('utf-8')


def parameters_string_to_dict(parameters):
    paramDict = {}
    if parameters:
        paramPairs = parameters[1:].split("&")
        for paramsPair in paramPairs:
            paramSplits = paramsPair.split('=')
            if (len(paramSplits)) == 2:
                paramDict[paramSplits[0]] = paramSplits[1]
    return paramDict


def addDir(name, url, mode, iconimage, type="", contextEnable=True):
    name = htmlParser.unescape(name)
    u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&type="+str(type)+"&thumb="+urllib.quote_plus(iconimage)
    ok = True

    liz = xbmcgui.ListItem(name, iconImage="DefaultTVShows.png", thumbnailImage=iconimage)
    liz.setInfo(type="video", infoLabels={"title": name})
    entries = []
    if "/MyList" in url:
        entries.append((translation(30122), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=addMyListToLibrary)',))
    liz.setProperty("fanart_image", defaultFanart)
    if contextEnable:
        liz.addContextMenuItems(entries)
    else:
        emptyEntries = []
        liz.addContextMenuItems(emptyEntries, replaceItems=True)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok


def addVideoDir(name, url, mode, iconimage, videoType="", desc="", duration="", year="", mpaa="", director="", genre="", rating=""):
##    if duration:
##        duration = str(int(duration) * 60)
    name = name.encode("utf-8")
    filename = clean_filename(url)+".jpg"
    coverFile = os.path.join(cacheFolderCoversTMDB, filename)
    fanartFile = os.path.join(cacheFolderFanartTMDB, filename)
    if os.path.exists(coverFile):
        iconimage = coverFile
    u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&thumb="+urllib.quote_plus(iconimage)
    ok = True
    liz = xbmcgui.ListItem(name, iconImage="DefaultTVShows.png", thumbnailImage=iconimage)
    liz.setInfo(type="video", infoLabels={"title": name, "plot": desc, "duration": duration, "year": year, "mpaa": mpaa, "director": director, "genre": genre, "rating": float(rating)})
    if os.path.exists(fanartFile):
        liz.setProperty("fanart_image", fanartFile)
    elif os.path.exists(coverFile):
        liz.setProperty("fanart_image", coverFile)
    entries = []
    if videoType == "tvshow":
        if browseTvShows:
            entries.append((translation(30121), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=playVideoMain&url='+urllib.quote_plus(url)+'&thumb='+urllib.quote_plus(iconimage)+')',))
        else:
            entries.append((translation(30118), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=listSeasons&url='+urllib.quote_plus(url)+'&thumb='+urllib.quote_plus(iconimage)+')',))
    if videoType != "episode":
        entries.append((translation(30134), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=playTrailer&url='+urllib.quote_plus(name)+')',))
        entries.append((translation(30114), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=addToQueue&url='+urllib.quote_plus(url)+')',))
        entries.append((translation(30140), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=listVideos&url='+urllib.quote_plus(urlMain+"/WiMovie/"+url)+'&type=movie)',))
        entries.append((translation(30141), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=listVideos&url='+urllib.quote_plus(urlMain+"/WiMovie/"+url)+'&type=tv)',))
    if videoType == "tvshow":
        entries.append((translation(30122), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=addSeriesToLibrary&url=&name='+urllib.quote_plus(name.strip())+'&seriesID='+urllib.quote_plus(url)+')',))
    elif videoType == "movie":
        entries.append((translation(30122), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=addMovieToLibrary&url='+urllib.quote_plus(url)+'&name='+urllib.quote_plus(name.strip()+' ('+year+')')+')',))
    liz.addContextMenuItems(entries)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok


def addVideoDirR(name, url, mode, iconimage, videoType="", desc="", duration="", year="", mpaa="", director="", genre="", rating=""):
##    if duration:
##        duration = str(int(duration) * 60)
    name = name.encode("utf-8")
    filename = clean_filename(url)+".jpg"
    coverFile = os.path.join(cacheFolderCoversTMDB, filename)
    fanartFile = os.path.join(cacheFolderFanartTMDB, filename)
    if os.path.exists(coverFile):
        iconimage = coverFile
    u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&thumb="+urllib.quote_plus(iconimage)
    ok = True
    liz = xbmcgui.ListItem(name, iconImage="DefaultTVShows.png", thumbnailImage=iconimage)
    liz.setInfo(type="video", infoLabels={"title": name, "plot": desc, "duration": duration, "year": year, "mpaa": mpaa, "director": director, "genre": genre, "rating": float(rating)})
    if os.path.exists(fanartFile):
        liz.setProperty("fanart_image", fanartFile)
    elif os.path.exists(coverFile):
        liz.setProperty("fanart_image", coverFile)
    entries = []
    if videoType == "tvshow":
        if browseTvShows:
            entries.append((translation(30121), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=playVideoMain&url='+urllib.quote_plus(url)+'&thumb='+urllib.quote_plus(iconimage)+')',))
        else:
            entries.append((translation(30118), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=listSeasons&url='+urllib.quote_plus(url)+'&thumb='+urllib.quote_plus(iconimage)+')',))
    entries.append((translation(30134), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=playTrailer&url='+urllib.quote_plus(name)+')',))
    entries.append((translation(30115), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=removeFromQueue&url='+urllib.quote_plus(url)+')',))
    entries.append((translation(30140), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=listVideos&url='+urllib.quote_plus(urlMain+"/WiMovie/"+url)+'&type=movie)',))
    entries.append((translation(30141), 'Container.Update(plugin://plugin.video.netflixbmc/?mode=listVideos&url='+urllib.quote_plus(urlMain+"/WiMovie/"+url)+'&type=tv)',))
    if videoType == "tvshow":
        entries.append((translation(30122), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=addSeriesToLibrary&url=&name='+str(name.strip())+'&seriesID='+str(url)+')',))
    elif videoType == "movie":
        entries.append((translation(30122), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=addMovieToLibrary&url='+urllib.quote_plus(url)+'&name='+str(name.strip()+' ('+year+')')+')',))
    liz.addContextMenuItems(entries)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok


def addSeasonDir(name, url, mode, iconimage, seriesName, seriesID):
    filename = clean_filename(seriesID)+".jpg"
    fanartFile = os.path.join(cacheFolderFanartTMDB, filename)
    coverFile = os.path.join(cacheFolderCoversTMDB, filename)
    u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&seriesID="+urllib.quote_plus(seriesID)
    ok = True
    liz = xbmcgui.ListItem(name, iconImage="DefaultTVShows.png", thumbnailImage=iconimage)
    liz.setInfo(type="video", infoLabels={"title": name})
    if os.path.exists(fanartFile):
        liz.setProperty("fanart_image", fanartFile)
    elif os.path.exists(coverFile):
        liz.setProperty("fanart_image", coverFile)
    entries = []
    entries.append((translation(30122), 'RunPlugin(plugin://plugin.video.netflixbmc/?mode=addSeriesToLibrary&url='+urllib.quote_plus(url)+'&name='+str(seriesName.strip())+'&seriesID='+str(seriesID)+')',))
    liz.addContextMenuItems(entries)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok


def addEpisodeDir(name, url, mode, iconimage, desc="", duration="", season="", episodeNr="", seriesID="", playcount=""):
##    if duration:
##        duration = str(int(duration) * 60)
    filename = clean_filename(seriesID)+".jpg"
    fanartFile = os.path.join(cacheFolderFanartTMDB, filename)
    coverFile = os.path.join(cacheFolderCoversTMDB, filename)
    u = sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)
    ok = True
    liz = xbmcgui.ListItem(name, iconImage="DefaultTVShows.png", thumbnailImage=iconimage)
    liz.setInfo(type="video", infoLabels={"title": name, "plot": desc, "duration": duration, "season": season, "episode": episodeNr, "playcount": playcount})
    if os.path.exists(fanartFile):
        liz.setProperty("fanart_image", fanartFile)
    elif os.path.exists(coverFile):
        liz.setProperty("fanart_image", coverFile)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)
    return ok


class window(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        self._stopEvent = threading.Event()
        self._wakeUpThread = threading.Thread(target=self._wakeUpThreadProc)
        self._wakeUpThread.start()

    def _wakeUpThreadProc(self):
        while not self._stopEvent.is_set():
            if debug:
                print "Netflixbmc: Sending wakeup to main UI to avoid idle/DPMS..."
            xbmc.executebuiltin("playercontrol(wakeup)")
            # bit of a hack above: wakeup is actually not a valid playercontrol argument,
            # but there's no error printed if the argument isn't found and any playercontrol
            # causes the DPMS/idle timeout to reset itself
            self._stopEvent.wait(60)
        if debug:
            print "Netflixbmc: wakeup thread finishing."

    def stopWakeupThread(self):
        if debug:
            print "Netflixbmc: stopping wakeup thread"
        self._stopEvent.set()
        self._wakeUpThread.join()

    def close(self):
        if debug:
            print "Netflixbmc: closing dummy window"
        self.stopWakeupThread()
        xbmcgui.WindowXMLDialog.close(self)

    def onAction(self, action):
        ACTION_SELECT_ITEM = 7
        ACTION_PARENT_DIR = 9
        ACTION_PREVIOUS_MENU = 10
        ACTION_PAUSE = 12
        ACTION_STOP = 13
        ACTION_SHOW_INFO = 11
        ACTION_SHOW_GUI = 18
        ACTION_MOVE_LEFT = 1
        ACTION_MOVE_RIGHT = 2
        ACTION_MOVE_UP = 3
        ACTION_MOVE_DOWN = 4
        ACTION_PLAYER_PLAY = 79
        ACTION_VOLUME_UP = 88
        ACTION_VOLUME_DOWN = 89
        ACTION_MUTE = 91
        ACTION_CONTEXT_MENU = 117
        ACTION_BUILT_IN_FUNCTION = 122
        KEY_BUTTON_BACK = 275
        if not remoteControl and action != ACTION_BUILT_IN_FUNCTION:
            # if we're not passing remote control actions, any non-autogenerated
            # remote action that reaches here is a signal to close this dummy
            # window as Chrome is gone
            if debug:
                print "Netflixbmc: Closing dummy window after action %d" % (action.getId())
            self.close()
            return

        if osWin:
            proc = subprocess.Popen('WMIC PROCESS get Caption', shell=True, stdout=subprocess.PIPE)
            procAll = ""
            for line in proc.stdout:
                procAll+=line
            if "chrome.exe" in procAll:
                if action in [ACTION_SHOW_INFO, ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_BUTTON_BACK]:
                    subprocess.Popen('"'+sendKeysPath+'"'+' sendKey=Close', shell=False)
                    self.close()
                elif action==ACTION_SELECT_ITEM:
                    subprocess.Popen('"'+sendKeysPath+'"'+' sendKey=PlayPause', shell=False)
                elif action==ACTION_MOVE_LEFT:
                    subprocess.Popen('"'+sendKeysPath+'"'+' sendKey=SeekLeft', shell=False)
                elif action==ACTION_MOVE_RIGHT:
                    subprocess.Popen('"'+sendKeysPath+'"'+' sendKey=SeekRight', shell=False)
                elif action==ACTION_MOVE_UP:
                    subprocess.Popen('"'+sendKeysPath+'"'+' sendKey=VolumeUp', shell=False)
                elif action==ACTION_MOVE_DOWN:
                    subprocess.Popen('"'+sendKeysPath+'"'+' sendKey=VolumeDown', shell=False)
            else:
                self.close()
        elif osLinux:
            doClose = False
            key=None
            if action in [ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_BUTTON_BACK]:
                key="control+shift+q"
                doClose=True
            elif action in [ ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY, ACTION_PAUSE ]:
                key="space"
            elif action==ACTION_MOVE_LEFT:
                key="Left"
            elif action==ACTION_MOVE_RIGHT:
                key="Right"
            elif action==ACTION_SHOW_INFO:
                key="question"
            elif action==ACTION_VOLUME_UP:
                key="Up"
            elif action==ACTION_VOLUME_DOWN:
                key="Down"
            elif action==ACTION_MUTE:
                key="M"
            elif action==ACTION_CONTEXT_MENU:
                key="ctrl+alt+shift+d"
            elif debug:
                print "Netflixbmc: unmapped key action=%d" % (action.getId())
            if key is not None:
                p = subprocess.Popen('xdotool search --onlyvisible --class "google-chrome|Chromium" key %s' % key, shell=True)
                p.wait()
                # 0 for success, 127 if xdotool not found in PATH. Return code is 1 if window not found (indicating should close).
                if not p.returncode in [0,127] or doClose:
                    self.close()
                if debug:
                    print "Netflixbmc: remote action=%d key=%s xdotool result=%d" % (action.getId(), key, p.returncode)
        elif osOSX:
            proc = subprocess.Popen('/bin/ps ax', shell=True, stdout=subprocess.PIPE)
            procAll = ""
            for line in proc.stdout:
                procAll+=line
            if "chrome" in procAll:
                if action in [ACTION_SHOW_INFO, ACTION_SHOW_GUI, ACTION_STOP, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_BUTTON_BACK]:
                    subprocess.Popen('cliclick kd:cmd t:q ku:cmd', shell=True)
                    self.close()
                elif action==ACTION_SELECT_ITEM:
                    subprocess.Popen('cliclick t:p', shell=True)
                elif action==ACTION_MOVE_LEFT:
                    subprocess.Popen('cliclick kp:arrow-left', shell=True)
                elif action==ACTION_MOVE_RIGHT:
                    subprocess.Popen('cliclick kp:arrow-right', shell=True)
                elif action==ACTION_MOVE_UP:
                    subprocess.Popen('cliclick kp:arrow-up', shell=True)
                elif action==ACTION_MOVE_DOWN:
                    subprocess.Popen('cliclick kp:arrow-down', shell=True)
            else:
                self.close()
        elif osAndroid:
            pass #I don't know if we can do this on android, We also may not need to as the netflix app should respond to remotes


params = parameters_string_to_dict(sys.argv[2])
mode = urllib.unquote_plus(params.get('mode', ''))
url = urllib.unquote_plus(params.get('url', ''))
thumb = urllib.unquote_plus(params.get('thumb', ''))
name = urllib.unquote_plus(params.get('name', ''))
season = urllib.unquote_plus(params.get('season', ''))
seriesID = urllib.unquote_plus(params.get('seriesID', ''))
type = urllib.unquote_plus(params.get('type', ''))

#if the addon is requested from the homewindow, assume the content is retrieved as widget so disable progress bar and forcedviews
runAsWidget = urllib.unquote_plus(params.get('widget', '')) == 'true'

if mode == 'main':
    main(type)
elif mode == 'wiHome':
    wiHome(type)
elif mode == 'listVideos':
    listVideos(url, type, runAsWidget)
elif mode == 'listSliderVideos':
    listSliderVideos(url, type, runAsWidget)
elif mode == 'listSearchVideos':
    listSearchVideos(url, type, runAsWidget)
elif mode == 'addToQueue':
    addToQueue(url)
elif mode == 'removeFromQueue':
    removeFromQueue(url)
elif mode == 'playVideo':
    playVideo(url)
elif mode == 'playVideoMain':
    playVideoMain(url)
elif mode == 'search':
    search(type)
elif mode == 'login':
    login()
elif mode == 'chooseProfile':
    chooseProfile()
elif mode == 'listGenres':
    listGenres(url, type)
elif mode == 'listTvGenres':
    listTvGenres(type)
elif mode == 'listViewingActivity':
    listViewingActivity(type, runAsWidget)
elif mode == 'listSeasons':
    listSeasons(name, url, thumb)
elif mode == 'listEpisodes':
    listEpisodes(seriesID, url)
elif mode == 'configureUtility':
    configureUtility()
elif mode == 'chromePluginOptions':
    chromePluginOptions()
elif mode == 'deleteCookies':
    deleteCookies()
elif mode == 'deleteCache':
    deleteCache()
elif mode == 'deleteChromeUserData':
    deleteChromeUserDataFolder()
elif mode == 'resetAddon':
    resetAddon()
elif mode == 'playTrailer':
    playTrailer(url)
elif mode == 'addMyListToLibrary':
    addMyListToLibrary()
elif mode == 'addMovieToLibrary':
    addMovieToLibrary(url, name)
elif mode == 'addSeriesToLibrary':
    addSeriesToLibrary(seriesID, name, url)
elif mode == 'profileDisplayUpdate':
    profileDisplayUpdate()
else:
    index()


if trace_on:
    pydevd.stoptrace()
