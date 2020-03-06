from machine import UART, RTC, Pin
import ntptime
import machine
import time
from struct import *
import network
import ubinascii
from umqtt.simple import MQTTClient
try:
  import usocket as socket
except:
  import socket
from main.ota_updater import OTAUpdater

def zfill(s, width):
    if len(s) < width:
        return ("0" * (width - len(s))) + s
    else:
        return s
 
def decoded_measurement(data,parametro):
    #print(" ".join("{:02x}".format(c) for c in data))
    parametro="".join("{:02x}".format(ord(c)) for c in parametro)
    recv = "".join("{:02x}".format(c) for c in data)
    metre = [None] * 2
    if ((recv[0] != 'a') | (parametro[1] != recv[1])):
      print("Error recibido")
      return metre
    if ((recv[1] == '0') | (recv[1] == '1')):##Voltaje o corriente
      for i in range(2):
        metre[i] = data[i+2]
        metre[i] = zfill(hex(metre[i]).split('x')[-1],2)
    if (recv[1] == '3'):
      metre = [None] * 3
      for i in range(3):
        metre[i] = data[i+1]
        metre[i] = zfill(hex(metre[i]).split('x')[-1],2)
    return metre

def read_pzem(address,parametro):
    data= address.split('.')
    if len(data) != 4:
      print("Address incorrecta")
      return 0
    param ='\xb0'+'\xb1'+'\xb2'+'\xb3'+'\xb4'
    try:
      if param.find(parametro) == -1:
        print("Solicitud de parametro incorrecta")
        return 0
    except:
      print("Parametro inadecuado")
      return 0 
    msg = parametro
    for i in data:
      msg += chr(int(i))
    msg += '\x00'
    msg += check_sum(msg)
    msg = bytes([ord(char) for char in msg])
    return msg    

def check_sum(data):
  checksum = 0
  for ch in data:
    checksum += ord(ch)
  return chr(checksum%256)

def set_address(addr,addr_old):
    if ((addr <= '\xf7') & (addr >= '\x01') & (addr_old <= '\xf8') & (addr_old >= '\x01')) :
         data = addr_old+'\x06'+'\x00'+'\x02'+'\x00'+ addr
         crc = INITIAL_MODBUS
         for ch in data:
             crc = calcByte( ch, crc)
         crc = zfill(bin(crc)[2:],16)
         put_crc = ''        
         for i in range(0,len(crc),8):
             put_crc += chr(int(crc[i:i+8],2))
         data = data + rev(put_crc)#[::-1]
         temp = bytes()
         for i in data:
           temp += bytes([ord(i)])
         return temp

def write_wifi_data(essid,password):
  file = open('data_wifi.txt','w')
  file.write(essid + ' ' +password)
  file.close()
  
def erase_wifi_data():
  file = open('data_wifi.txt','w')
  file.close()
  
def read_wifi_data():
  file = open('data_wifi.txt','r')
  data = file.read()
  if not data:
    essid = ''
    passw = ''
  else:
    essid,passw=data.split(" ")
  return essid, passw
  
def connect(ssid,password):
  #ssid = "WeWork"
  #password = "P@ssw0rd" 
  station = network.WLAN(network.STA_IF) 
  if station.isconnected() == True:
    print("Already connected") 
    write_wifi_data(ssid,password)   
    return 
  station.active(True)
  station.connect(ssid, password)
  for t in range (0,16):
    if t == 15:
      print("Sali")      
      station.disconnect()
      station.active(False)
      time.sleep(0.5)
      erase_wifi_data()
      machine.reset()
    elif station.isconnected() == False:
      print ("Aun no conectado")     
      time.sleep(12)
    else:
      print ("Me conecte")
      write_wifi_data(ssid,password)
      break  
  print("Connection successful")
  print(station.ifconfig())
  return 
  
def web_page(id_device,id_mensaje):
  html = """<html><head> <title>Web Server NIMBLU Checkinwatt</title> <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,"> <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
  h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #4286f4; border: none;
  border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
  </style> </head> <body> <h1>Web Server NIMBLU Checkinwatt</h1> <p>Configuracion de cliente WIFI: </p>
  <p><strong>ID device Azure IoT Hub: """ + id_device + """</strong></p> <form method = "post" enctype="multipart/form-data" accept-charset="UTF-8"> <table border="1" style="margin: 0 auto;"> <tr><td>
  <p style="color:#0F3376";>ESSID :<input type="text" style="text-align:center" name="essid"></p>
  <p style="color:#0F3376";>PASSWORD :<input type="password" style="text-align:center" name="password"></p> </td></tr>
  </table><p><button class="button">Conectar</button></p> <p style="color:rgb(255,0,0);"><strong>"""+id_mensaje+""" </strong></p></form> </body></html>"""
  return html
  
def ap_mode(led): 
  led.value(0) 
  ap = network.WLAN(network.AP_IF)
  mac = ubinascii.hexlify(network.WLAN().config('mac'),':').decode()
  mac = mac.upper()
  ap.active(True)
  ap.config(essid='Nimblu_chekinwatts('+mac[-8:]+')', authmode=network.AUTH_WPA_WPA2_PSK, password='12345678')
  ap.ifconfig(('192.168.0.1', '255.255.255.0', '192.168.0.1', '192.168.0.1'))
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.bind(('0.0.0.0', 80))
  s.listen(2)
  while True:
    conn, addr = s.accept()
    print('Got a connection from %s' % str(addr))
    request = conn.recv(1024)
    request = str(request)
    print('Content = %s' % request)
    ptr1 = request.find('essid')
    ptr2 = request.find('password')
    if ((ptr1 != -1) | (ptr2 != -1)):         
      essid = request[ptr1+14:ptr2-86]
      password =request[ptr2+17:-51]
      if essid: 
        mensaje="Intentando conexion a AP sugerido"
        response = web_page(mac,mensaje)
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)
        conn.close()
        s.close()
        ap.active(False)
        print('Pasar a modo cliente')
        return essid,password
    mensaje=""
    response = web_page(mac,mensaje)
    conn.send('HTTP/1.1 200 OK\n')
    conn.send('Content-Type: text/html\n')
    conn.send('Connection: close\n\n')
    conn.sendall(response)
    conn.close()

def iot_hub_mqttsend(device_id, hostname,username,password,msg):
  #logging.basicConfig(level=logging.ERROR)
  #logger.setLevel(logging.ERROR)
  client = MQTTClient(device_id, hostname, user=username, password=password,
                    ssl=True, port=8883)
  try:
    client.connect()
    topic = "devices/{device_id}/messages/events/".format(device_id=device_id)
    client.publish(topic, msg, qos=1)
    client.disconnect()
  except Exception as e:
    error = str(e.args[0])
    try:
      client.disconnect()
    except:
      print("No habia que desconectar el cliente")    
    print("Error en la conexion a IoT Hub")
    letter = [device_id,"MQTTException",error,str(time.time())]
    print (letter)
    try:
      send_mail(letter)
    except:
      print("No se pudo enviar el correo")    
    time.sleep(5)
   
def json_format(seg,character,measurent):
  k = 2
  if (seg == 62):
    k = 3
  for i in range(k):
    character +=  measurent[i] 
  return character
  
def adjustment_time(UTC):
  ntptime.settime() 
  (year, month, mday, week_of_year, hour, minute, second, milisecond)=RTC().datetime()
  RTC().init((year, month, mday, week_of_year, hour+UTC, minute, second, milisecond))
  print ("Fecha/Hora (year, month, mday, week of year, hour, minute, second, milisecond):", RTC().datetime())
  
def send_mail(letter):
  try:
    import main.umail as umail
  except:
    return
  smtp = umail.SMTP('smtp.gmail.com', 587, username='checkinwattsnimblu@gmail.com', password='Qwerty123.')
  smtp.to('checkinwattsnimblu@gmail.com')
  print("Enviando correo")
  smtp.write("Subject: Error_log\n\n")
  for i in letter:
    smtp.write(i+"\n")
  smtp.write("...\n")
  smtp.send()
  smtp.quit()
  return  

def check_time_update_github(last_update):
  next_update = last_update+24*3600
  print(next_update)
  if next_update < time.mktime(time.localtime()):
    print("Hora de revisar actualizacion")
    return True
  else:
    return False

def download_and_install_update_if_available(url,ssid,password):
     o = OTAUpdater(url)
     o.download_and_install_update_if_available(ssid,password)
  
########################################################
def main():
  global time_last_update
  time_last_update = 0
  url='https://github.com/Yoendric/checkinwatt'
  o = OTAUpdater(url)
  led=Pin(14,Pin.OUT)
  try:
    ssid,passw = read_wifi_data()
  except:
    ssid,passw = ("","")
  if ((not ssid) | (not passw)):
    ssid , passw = ap_mode(led) 
  connect(ssid,passw)
  download_and_install_update_if_available(url,ssid,passw)
  try:
    adjustment_time(-5)
  except:
    print("no se pudo ajustar RTC")
  uart = UART(2, baudrate=9600, tx=18,rx=19)# init with given baudrate
  uart.init(9600, bits=8, parity=None, stop=1) # init with given parameters
  uart1 = UART(1, baudrate=9600, tx=17,rx=16)# init with given baudrate
  uart1.init(9600, bits=8, parity=None, stop=1) # init with given parameters
  # Azure IoT-hub settings
  hostname = "CheckinWattsHub.azure-devices.net"
  #This needs to be the key of the "device" IoT-hub shared access policy, NOT the device
  #primary_key = "XXXXXXXXXXXXXX"
  device_id = ubinascii.hexlify(network.WLAN().config('mac'),':').decode()
  device_id = device_id.upper()
  uri = "{hostname}/devices/{device_id}".format(hostname=hostname, device_id=device_id)
  password = "SharedAccessSignature sr=CheckinWattsHub.azure-devices.net%2Fdevices%2FB4%253AE6%253A2D%253AEB%253A64%253A6D&sig=GAJt50FAe2w7CVauKHl1yW6zzMI1UMjp2VMM9HA5AIc%3D&se=1605029220"
  username_fmt = "{}/{}/?api-version=2018-06-30"
  username = username_fmt.format(hostname, device_id)
  version = "01000103"
  no_comunication_sensor=["FF","FF","FF"]
  while True:
    if check_time_update_github(time_last_update):
      try:
        o.check_for_update_to_install_during_next_reboot()
        time_last_update=time.mktime(time.localtime())
      except:
        print("NO SE PUEDE CONECTAR PARA VER SI HAY ACTUALIZACION") 
    f0 = ""
    f1 = f0
    MSG_TXT = '{{"ID": "{version}","F0": "{f0}","F1": "{f1}"}}'
    seg = 1
    while seg <= 62:
      led.value(seg%2)
      if seg == 1:
        meas='\xb0'
      elif seg == 62:
        meas = '\xb3'
      else:
        meas = '\xb1'
      data = read_pzem('192.168.1.1',meas)
      uart.write(data)
      data = ''
      time.sleep(0.1)
      data = uart.read()
      if not data:
        print('No comunicacion con PZEM-004T-01: Segundo: '+str(seg))
        f0=json_format(seg,f0,no_comunication_sensor)
      else:  
        print('PZEM-004T-01: Segundo: '+str(seg))
        measurent= decoded_measurement(data[0:-3],meas)
        f0=json_format(seg,f0,measurent) 
      data = read_pzem('192.168.1.1',meas)
      uart1.write(data)
      data = ''
      time.sleep(0.1)
      data = uart1.read()
      if not data:
        print('No comunicacion con PZEM-004T-02: Segundo: '+str(seg))
        f1=json_format(seg,f1,no_comunication_sensor)
      else:  
        print('PZEM-004T-02: Segundo: '+str(seg))    
        measurent= decoded_measurement(data[0:-3],meas)
        f1=json_format(seg,f1,measurent) 
      time.sleep(0.8)      
      seg = seg + 1
    msg_txt_formatted = MSG_TXT.format(version=version, f0=f0,f1=f1) 
    print ("Message ready to ship to IoT Hub Azure") 
    print (msg_txt_formatted)
    iot_hub_mqttsend(device_id, hostname,username,password,msg_txt_formatted) 
