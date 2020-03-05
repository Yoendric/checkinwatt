from main.ota_updater import OTAUpdater
import time
import machine

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

def main():
  o = OTAUpdater('https://github.com/Yoendric/checkinwatt')
  using_network('WeWork', 'P@ssw0rd')  
  cont=0
  while True:
    print("Esto es una prueba")
    cont = cont + 1
    if cont == 5:
       o.check_for_update_to_install_during_next_reboot()
    time.sleep(60)
 

