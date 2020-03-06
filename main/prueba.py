from main.ota_updater import OTAUpdater
import time
import machine
from machine import RTC
import ntptime

def using_network(ssid, password):
  import network
  sta_if = network.WLAN(network.STA_IF)
  if not sta_if.isconnected():
    print('connecting to network...')
    sta_if.active(True)
    sta_if.connect(ssid, password)
    while not sta_if.isconnected():
      pass
  print('network config:', sta_if.ifconfig())

def adjustment_time(UTC):
  ntptime.settime() 
  (year, month, mday, week_of_year, hour, minute, second, milisecond)=RTC().datetime()
  RTC().init((year, month, mday, week_of_year, hour+UTC, minute, second, milisecond))
  print ("Fecha/Hora (year, month, mday, week of year, hour, minute, second, milisecond):", RTC().datetime())

def zfill(s, width):
    if len(s) < width:
        return ("0" * (width - len(s))) + s
    else:
        return s

def check_time_update_github(hora,min,last_update):
  (year, month, mday, week_of_year, hour, minute, second, milisecond)=RTC().datetime()
  hora_ref_epoch=time.mktime((year, month, mday, week_of_year, hora, min, second, milisecond))
  if hora_ref_epoch > time.mktime(time.localtime()):
    next_transmision = hora_ref_epoch
  else:
    next_transmision = last_update+3600*24
  if next_transmision < time.mktime(time.localtime()):
    print("Hora de revisar actualizacion")
    return True
  else:
    return False
  
def main():
  global time_last_update
  time_last_update = 0
  o = OTAUpdater('https://github.com/Yoendric/checkinwatt')
  using_network('INFINITUM649F_2.4', 'RG9fMasNh3')  
  adjustment_time(-6)
  while True:
    print("Esto es una prueba")
    if check_time_update_github(10,0,time_last_update):
       o.check_for_update_to_install_during_next_reboot()
       time_last_update=time.mktime(time.localtime()) 
    time.sleep(60)