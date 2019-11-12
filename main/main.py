from ota_update.main.ota_updater import OTAUpdater


 def download_and_install_update_if_available():
     o = OTAUpdater('https://github.com/Yoendric/checkinwatt')
     o.download_and_install_update_if_available('WeWork', 'P@ssw0rd')


 def start():
     import time
     while True:
       print("Esto es una prueba")
       time.sleep(5)


 def boot():
     download_and_install_update_if_available()
     start()


 boot()
