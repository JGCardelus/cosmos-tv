import os
import json
import time
import keyboard

from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


import server
import config
import framework as fmk
from services.show import Show, Episode, Season

# LOAD CONFIGURATION
username = None
password = None
netflix_user = None
if config.settings_path != None:
    if os.path.isfile(config.settings_path):
        settings_file = open(config.settings_path, 'r')
        settings = json.loads(settings_file.read())

        for app in settings["apps"]:
            if app["name"] == "netflix":
                username = app["username"]
                password = app["password"]
                netflix_user = app["netflix-user"]

class Netflix:
    def __init__(self, driver, window_handles):
        # BASIC VARIABLES
        self.driver = driver
        self.window_handles = window_handles
        self.url = "https://www.netflix.com"
        self.name = "Netflix"
        self.id_ = "netflix"

        # MEDIA VARIABLES
        self.is_show_on = False
        self.time = 0
        self.total_time = 0
        self.scan_result = None
        self.skip_intro_requested = False
        self.skip_outro_requested = False
        self.skip_button = None

        # OPENED APP VARIABLES
        self.created_open_app = False

        # SCAN SETTINGS
        self.shows = []
        self.show_name = None
        self.episode = None
        self.season = None

        self.max_scroll = 1
        self.last_show_parsed = 0
        self.show_parse_length = 15

        # LOAD SETTINGS
        self.username = username
        self.password = password
        self.netflix_user = netflix_user

    def get(self, url):
        self.driver.get(url)
        self.render_opened_app()
        self.render_show_info()
        self.focus()
        self.init_profile()

        self.scan(20)
        if len(self.shows) > 0:
            self.render_scan()

    def render_opened_app(self):
        parser = fmk.Parser()
        opened_app_json = None

        if not self.created_open_app:
            opened_app_json = parser.parse_open_app(self.name, "", self.id_)
            self.created_open_app = True
            server.emit("opened-apps", opened_app_json)
        else:
            opened_app_json = None
            if self.episode != None:
                opened_app_json = parser.parse_open_app(self.name, self.episode.name, self.id_)
            elif self.show_name != None:
                opened_app_json = parser.parse_open_app(self.name, self.show_name, self.id_)
            else:
                opened_app_json = parser.parse_open_app(self.name, "", self.id_)

            server.emit("opened-apps-update", opened_app_json)

    def render_scan(self):
        start = self.last_show_parsed
        end = self.last_show_parsed + self.show_parse_length
        if self.last_show_parsed + self.show_parse_length >= len(self.shows):
            end = len(self.shows)

        self.last_show_parsed = end
        if start != end:
            # Create parser object
            parser = fmk.Parser()
            shows_json = parser.parse_shows(self.shows[start:end])
            self.emit_scan_result(shows_json)

    def render_show_info(self):
        if self.episode != None:
            server.emit('show-name', self.episode.name)
            parser = fmk.Parser()
            info = parser.parse_season_episode_info(self.season.number, self.episode.number)
            server.emit('season-episode-info', info)
        elif self.show_name != None:
            server.emit('show-name', self.show_name)
            server.emit('season-episode-info', "")
        else:
            server.emit('show-name', self.name)
            server.emit('season-episode-info', "")

    def log_in(self):
        log_in_button = None
        try:
            log_in_button = self.driver.find_element_by_xpath('//a[@data-uia="header-login-link"]')
        except exceptions.NoSuchElementException:
            pass
        
        if log_in_button != None:
            log_in_button.click()
            username_input = self.driver.find_element_by_xpath('//input[@id="id_userLoginId"]')
            username_input.send_keys(self.username)
            password_input = self.driver.find_element_by_xpath('//input[@id="id_password"]')
            password_input.send_keys(self.password)

            submit_log_in = self.driver.find_element_by_xpath('//button[@data-uia="login-submit-button"]')
            submit_log_in.click()

        return log_in_button

    def select_user(self):
        profile_gate = None
        try:
            profile_gate = self.driver.find_element_by_xpath('//ul[@class="choose-profile"]')
        except exceptions.NoSuchElementException:
            pass

        if profile_gate != None:
            profiles = self.driver.find_elements_by_xpath('//a[@class="profile-link"]')
            netflix_users = self.driver.find_elements_by_xpath('//span[@class="profile-name"]')
            for i, netflix_user in enumerate(netflix_users):
                if self.netflix_user == netflix_user.get_attribute('innerHTML'):
                    profiles[i].click()
                    break

        return profile_gate

    def init_profile(self):
        # FIND LOG-IN
        log_in = self.log_in()
        profile_gate = self.select_user()

        if log_in == None and profile_gate == None:
            time.sleep(1) # Change, wait until page loads

    def scroll_page(self):
        height = int(self.driver.execute_script("return document.body.offsetHeight"))
        counter = 0
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.offsetHeight);")
            time.sleep(1)
            new_height = int(self.driver.execute_script("return document.body.offsetHeight"))
            counter += 1
            if height != new_height:
                height = new_height
            else:
                break

            if counter == self.max_scroll:
                break

    def scan(self, max_scan_count):
        try:
            wait = fmk.Wait_Until(self.driver)
            # Wait until main page has been loaded
            wait.wait_xpath('//ul[@class="tabbed-primary-navigation"]')
            self.scroll_page()
            self.driver.execute_script("window.scrollTo(0, 0);")

            elements = self.driver.find_elements_by_class_name('slider-item')
            self.shows = []

            counter = 0
            if len(elements) < max_scan_count:
                max_scan_count = len(elements)

            while counter < max_scan_count:
                try:
                    element = elements[counter]
                    # SELECT ELEMENT
                    show_container = element.find_element_by_css_selector("p.fallback-text")
                    url_container = element.find_element_by_css_selector("a[role='link']")
                    # GET INFORMATION
                    show_name = show_container.get_attribute('innerHTML')
                    url = url_container.get_attribute('href')
                    # SAVE SHOW
                    show = Show(show_name, url, element)
                    self.shows.append(show)
                    
                except exceptions.NoSuchElementException:
                    pass
                    
                counter += 1
        except:
            pass

    def emit_scan_result(self, result_data):
        server.emit("scan-result", result_data)

    def start_show(self, name, url):
        show = None
        for iter_show in self.shows:
            if iter_show.name == name and iter_show.url == url:
                show = iter_show
                break
        
        if show != None:
            # Check if element contains episodes
            is_series = self.deep_scan(show)
            
            if not is_series:
                # It is not a series, open player
                self.get(show.url)
            else:
                # Create parser object
                parser = fmk.Parser()
                # Show the results
                scan_result = parser.parse_series(show)
                self.emit_scan_result(scan_result)
        else:
            self.get(url)

    def get_show_container(self, show):
        wait = fmk.Wait_Until(self.driver)
        expand_show = show.container.find_element_by_css_selector('div.bob-jawbone-chevron')
        expand_show.click()
        wait.wait_xpath("//li[@id='tab-Overview']")
        container = self.driver.find_element_by_xpath('//div[@class="jawBoneFadeInPlaceContainer"]')
        episodes_selector = container.find_element_by_css_selector('li#tab-Episodes')
        episodes_selector.click()

        return container

    def get_episode(self, season_episode):
        wait = fmk.Wait_Until(self.driver)
        # Get name
        wait.wait_css("div.episodeTitle p", container=season_episode)
        episode_name_container = season_episode.find_element_by_css_selector('div.episodeTitle p')
        episode_name = episode_name_container.get_attribute('innerHTML')
        
        # Get link
        wait.wait_xpath('//a[@data-uia="play-button"]', container=season_episode)
        episode_url_container = season_episode.find_element_by_css_selector('a[data-uia="play-button"]')
        episode_url = episode_url_container.get_attribute('href')
        
        # Get number
        wait.wait_css("div.episodeNumber span", container=season_episode)
        episode_number_container = season_episode.find_element_by_css_selector("div.episodeNumber span")
        episode_number = int(episode_number_container.get_attribute('innerHTML'))
        
        episode = Episode(episode_name, episode_url, episode_number)

        return episode

    def get_seasons_length(self, container):
        wait = fmk.Wait_Until(self.driver)
        # Iterate through seasons
        wait.wait_css('div.nfDropDown')
        dropbox = container.find_element_by_css_selector("div.nfDropDown")
        dropbox.click()
        wait.wait_css("a.sub-menu-link")
        seasons_buttons = self.driver.find_elements_by_css_selector("a.sub-menu-link")

        return len(seasons_buttons)

    def get_next_season(self, season_n):
        wait = fmk.Wait_Until(self.driver)
        if season_n > 0:
            # Click on the dropdown
            dropdown = self.driver.find_element_by_css_selector("div.nfDropDown")
            dropdown.click()
        
        # Click on season and get seasons name
        wait.wait_css("a.sub-menu-link")
        select_season = self.driver.find_elements_by_css_selector("a.sub-menu-link")
        season_name = select_season[season_n].get_attribute('innerHTML')
        select_season[season_n].click()

        season_info = season_name.split(' ')
        season_number = int(season_info[1])

        return season_number

    def deep_scan(self, show):
        is_series = False
        try:
            container = self.get_show_container(show)
            seasons_length = self.get_seasons_length(container)
            
            wait = fmk.Wait_Until(self.driver)
            for i in range(seasons_length):
                season_number = self.get_next_season(i)
                season = Season(season_number)
                
                episode_load_wait = WebDriverWait(self.driver, 10)
                element = episode_load_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.episodeWrapper div.episodeLockup div.episodeTitle')))

                container = self.driver.find_element_by_css_selector('div.episodesContainer')
                # print(container.get_attribute("innerHTML"))
                # Select episodes in container
                season_episodes = container.find_elements_by_css_selector('div.slider-item')

                for season_episode in season_episodes:
                    episode = self.get_episode(season_episode)
                    season.episodes.append(episode)

                show.seasons.append(season)

            is_series = True
        except exceptions.NoSuchElementException:
            pass

        return is_series

    def load_session(self):
        if self.skip_intro_requested or self.skip_outro_requested:
            server.emit("activate-skip", "skip")
        
        if self.is_show_on:
            self.update_show_info()

    def get_media_information(self):
        try:
            media_container = self.driver.find_element_by_css_selector('div.AkiraPlayer')
            media_screen = self.driver.find_element_by_css_selector('div.VideoContainer')
            if not self.is_show_on:
                self.is_show_on = True
                self.update_show_info()
            self.get_skip_button()
            
        except exceptions.NoSuchElementException:
            if self.is_show_on:
                self.is_show_on = False
                self.reset_media_info()

    def reset_media_info(self):
        self.season = None
        self.episode = None
        self.show_name = ""

        self.render_opened_app()
        self.render_show_info()

    def update_show_info(self):
        self.get_show_info()
        self.render_opened_app()
        self.render_show_info()
        
    def get_show_info(self):
        title_div = self.driver.find_element_by_css_selector('div.video-title h4')
        self.show_name = title_div.get_attribute('innerHTML')
        try:
            episode_info_container = self.driver.find_elements_by_css_selector('div.video-title span')
            season_info = episode_info_container[0].get_attribute('innerHTML')
            episode_name = episode_info_container[1].get_attribute('innerHTML')

            #Parse season info
            if season_info != "":
                season_info_chunks = season_info.split(':')
                season_number = "".join(list(season_info_chunks[0])[1:]) #S01
                episode_number = "".join(list(season_info_chunks[1])[1:]) #E01

                self.season = Season(season_number)
                self.episode = Episode(episode_name, None, episode_number)
        except exceptions.NoSuchElementException:
            #print title
            self.season = None
            self.episode = None

    def get_skip_button(self):
        self.get_skip_intro()
        self.get_skip_outro()

    def get_skip_intro(self):
        try:
            skip_button = self.driver.find_element_by_css_selector('div.skip-credits')
            if not self.skip_intro_requested:
                self.skip_button = skip_button
                self.skip_intro_requested = True

                server.emit("activate-skip", "skip")
        except exceptions.NoSuchElementException:
            if self.skip_intro_requested:
                self.skip_intro_requested = False
                server.emit("deactivate-skip", "skip")
        except exceptions.StaleElementReferenceException:
            if self.skip_intro_requested:
                self.skip_intro_requested = False
                server.emit("deactivate-skip", "skip")
    
    def get_skip_outro(self):
        try:
            skip_button = self.driver.find_element_by_css_selector('button[data-uia="next-episode-seamless-button"]')
            if not self.skip_outro_requested:
                self.skip_button = skip_button
                self.skip_outro_requested = True

                server.emit("activate-skip", "skip")
        except exceptions.NoSuchElementException:
            if self.skip_outro_requested:
                self.skip_outro_requested = False
                server.emit("deactivate-skip", "skip")
        except exceptions.StaleElementReferenceException:
            if self.skip_outro_requested:
                self.skip_outro_requested = False
                server.emit("deactivate-skip", "skip")

    def skip(self):
        if self.skip_outro_requested or self.skip_intro_requested:
            try:
                self.skip_button.click()
                self.skip_requested = False
            except exceptions.StaleElementReferenceException:
                print("Element has gone stale")

    def fullscreen(self):
        if self.is_show_on:
            fmk.keyboard.press(fmk.k_key.f11)
            fmk.keyboard.release(fmk.k_key.f11)
        else:
            server.raise_not("Select a show first")

    def play(self):
        if self.is_show_on:
            fmk.keyboard.press(fmk.k_key.space)
            fmk.keyboard.release(fmk.k_key.space)
        else:
            server.raise_not("Select a show first")

    def next_show(self):
        if self.is_show_on:
            try:
                fmk.mouse.move(10, 10)
                next_show_button = self.driver.find_element_by_css_selector('button.button-nfplayerNextEpisode')
                next_show_button.click()
            except exceptions.NoSuchElementException:
                server.raise_not("This episode does not allow this action")
                pass
        else:
            server.raise_not("Select a show first")

    def forwards(self):
        if self.is_show_on:
            fmk.keyboard.press(fmk.k_key.right)
            fmk.keyboard.release(fmk.k_key.right)
        else:
            server.raise_not("Select a show first")

    def backwards(self):
        if self.is_show_on:
            fmk.keyboard.press(fmk.k_key.left)
            fmk.keyboard.release(fmk.k_key.left)
        else:
            server.raise_not("Select a show first")

    def focus(self):
        self.driver.maximize_window()
       
    def close(self):
        self.driver.quit()