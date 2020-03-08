from machine import UART, RTC, Pin
import ntptime
import machine
import time
from time import sleep
from struct import *
import network
import ubinascii
from umqtt.simple import MQTTClient
import collections
import re
from uhashlib import sha256
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
  
def connect_wifi_client(ssid,password):
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
      #send_mail(letter)
      print("EEEEEEEEE enviar correo")
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
  
def Adjustment_Time_RTC(UTC):
  while True:
    try:
      ntptime.settime() 
      (year, month, mday, week_of_year, hour, minute, second, milisecond)=RTC().datetime()
      RTC().init((year, month, mday, week_of_year, hour+UTC, minute, second, milisecond))
      print ("Fecha/Hora (year, month, mday, week of year, hour, minute, second, milisecond):", RTC().datetime())
      return
    except:
      print("ERROR ajustando RTC. Wait 1 second")
      time.sleep(1)  
  
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
  if next_update < time.mktime(time.localtime()):
    print("Hora de revisar actualizacion")
    return True
  else:
    return False

def download_and_install_update_if_available(url,ssid,password):
     o = OTAUpdater(url)
     o.download_and_install_update_if_available(ssid,password)

def Get_Client_Wifi_Parameters(led):
  try:
    ssid,passw = read_wifi_data()
  except:
    ssid,passw = ("","")
  if ((not ssid) | (not passw)):
    ssid , passw = ap_mode(led)
  return ssid,passw

def Read_PZEM_and_Estruct_Message(led,uart,uart1):
  COM_UART=[uart,uart1]
  version = "01000103"
  no_comunication_sensor=["FF","FF","FF"]
  f0 = ""
  f1 = f0
  MSG_TXT = '{{"ID": "{version}","F0": "{f0}","F1": "{f1}"}}'
  seg = 1
  while seg <= 62:
    led.value(seg%2)
    if seg == 1:
      meas = '\xb0'
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
  return msg_txt_formatted

def b64encode(s, altchars=None):
    bytes_types = (bytes, bytearray)
    if not isinstance(s, bytes_types):
        raise TypeError("expected bytes, not %s" % s.__class__.__name__)
    # Strip off the trailing newline
    encoded = ubinascii.b2a_base64(s)[:-1]
    if altchars is not None:
        if not isinstance(altchars, bytes_types):
            raise TypeError("expected bytes, not %s"
                            % altchars.__class__.__name__)
        assert len(altchars) == 2, repr(altchars)
        return encoded.translate(bytes.maketrans(b'+/', altchars))
    return encoded

def b64decode(s, altchars=None, validate=False):
    s = _bytes_from_decode_data(s)
    if altchars is not None:
        altchars = _bytes_from_decode_data(altchars)
        assert len(altchars) == 2, repr(altchars)
        s = s.translate(bytes.maketrans(altchars, b'+/'))
    if validate and not re.match(b'^[A-Za-z0-9+/]*={0,2}$', s):
        raise ubinascii.Error('Non-base64 digit found')
    return ubinascii.a2b_base64(s)

def _bytes_from_decode_data(s):
    if isinstance(s, str):
        try:
            return s.encode('ascii')
#        except UnicodeEncodeError:
        except:
            raise ValueError('string argument should contain only ASCII characters')
    elif isinstance(s, bytes_types):
        return s
    else:
        raise TypeError("argument should be bytes or ASCII string, not %s" % s.__class__.__name__)

def quote(string, safe='/', encoding=None, errors=None):
    if isinstance(string, str):
        if not string:
            return string
        if encoding is None:
            encoding = 'utf-8'
        if errors is None:
            errors = 'strict'
        string = string.encode(encoding, errors)
    else:
        if encoding is not None:
            raise TypeError("quote() doesn't support 'encoding' for bytes")
        if errors is not None:
            raise TypeError("quote() doesn't support 'errors' for bytes")
    return quote_from_bytes(string, safe)

def quote_plus(string, safe='', encoding=None, errors=None):
    if ((isinstance(string, str) and ' ' not in string) or
        (isinstance(string, bytes) and b' ' not in string)):
        return quote(string, safe, encoding, errors)
    if isinstance(safe, str):
        space = ' '
    else:
        space = b' '
    string = quote(string, safe + space, encoding, errors)
    return string.replace(' ', '+')
  
def quote_from_bytes(bs, safe='/'):
    _ALWAYS_SAFE = frozenset(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                         b'abcdefghijklmnopqrstuvwxyz'
                         b'0123456789'
                         b'_.-')
    _ALWAYS_SAFE_BYTES = bytes(_ALWAYS_SAFE)
    _safe_quoters = {}
    if not isinstance(bs, (bytes, bytearray)):
        raise TypeError("quote_from_bytes() expected bytes")
    if not bs:
        return ''
    if isinstance(safe, str):
        # Normalize 'safe' by converting to bytes and removing non-ASCII chars
        safe = safe.encode('ascii', 'ignore')
    else:
        safe = bytes([c for c in safe if c < 128])
    if not bs.rstrip(_ALWAYS_SAFE_BYTES + safe):
        return bs.decode()
    try:
        quoter = _safe_quoters[safe]
    except KeyError:
        _safe_quoters[safe] = quoter = Quoter(safe).__getitem__
    return ''.join([quoter(char) for char in bs])
  
class Quoter(collections.defaultdict):
    def __init__(self, safe):
        """safe: bytes object."""
        _ALWAYS_SAFE = frozenset(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ' b'abcdefghijklmnopqrstuvwxyz'b'0123456789'b'_.-')
        self.safe = _ALWAYS_SAFE.union(safe)

    def __repr__(self):
        # Without this, will just display as a defaultdict
        return "<Quoter %r>" % dict(self)

    def __missing__(self, b):
        # Handle a cache miss. Store quoted string in cache and return.
        res = chr(b) if b in self.safe else '%{:02X}'.format(b)
        self[b] = res
        return res

def urlencode(query, doseq=False, safe='', encoding=None, errors=None):
    if hasattr(query, "items"):
        query = query.items()
    l = []
    if not doseq:
        for k, v in query:
            if isinstance(k, bytes):
                k = quote_plus(k, safe)
            else:
                k = quote_plus(str(k), safe, encoding, errors)

            if isinstance(v, bytes):
                v = quote_plus(v, safe)
            else:
                v = quote_plus(str(v), safe, encoding, errors)
            l.append(k + '=' + v)
    else:
        for k, v in query:
            if isinstance(k, bytes):
                k = quote_plus(k, safe)
            else:
                k = quote_plus(str(k), safe, encoding, errors)

            if isinstance(v, bytes):
                v = quote_plus(v, safe)
                l.append(k + '=' + v)
            elif isinstance(v, str):
                v = quote_plus(v, safe, encoding, errors)
                l.append(k + '=' + v)
            else:
                try:
                    # Is this a sufficient test for sequence-ness?
                    x = len(v)
                except TypeError:
                    # not a sequence
                    v = quote_plus(str(v), safe, encoding, errors)
                    l.append(k + '=' + v)
                else:
                    # loop over the sequence
                    for elt in v:
                        if isinstance(elt, bytes):
                            elt = quote_plus(elt, safe)
                        else:
                            elt = quote_plus(str(elt), safe, encoding, errors)
                        l.append(k + '=' + elt)
    return '&'.join(l)

def xor(x, y):
    return bytes(x[i] ^ y[i] for i in range(min(len(x), len(y))))

def hmac_sha256(key_K, data):
    if len(key_K) > 64:
        raise ValueError('The key must be <= 64 bytes in length')
    padded_K = key_K + b'\x00' * (64 - len(key_K))
    ipad = b'\x36' * 64
    opad = b'\x5c' * 64
    h_inner = sha256(xor(padded_K, ipad))
    h_inner.update(data)
    h_outer = sha256(xor(padded_K, opad))
    h_outer.update(h_inner.digest())
    return h_outer.digest()

def Sas_token(uri,key):
  expiry=3600*365*24
  ttl=time.time()+expiry+946684800
  sign_key = "%s\n%d" % ((quote_plus(uri)), int(ttl))
  datos=hmac_sha256(b64decode(key), sign_key.encode('utf-8'))
  signature = b64encode(hmac_sha256(b64decode(key), sign_key.encode('utf-8')))
  rawtoken={'sr':uri,'sig':signature}
  rawtoken['se']=str(int(ttl))
  password = 'SharedAccessSignature ' + urlencode(rawtoken)
  print(password)
  return password
  
def main():
  global time_last_update   #variable important to OTA time update
  time_last_update = 0
  url='https://github.com/Yoendric/checkinwatt'   #Github repository project
  o = OTAUpdater(url)
  led=Pin(14,Pin.OUT)
  ssid,passw=Get_Client_Wifi_Parameters(led)
  connect_wifi_client(ssid,passw)
  download_and_install_update_if_available(url,ssid,passw)
  Adjustment_Time_RTC(-6)
  uart = UART(2, baudrate=9600, tx=18,rx=19)# init with given baudrate
  uart.init(9600, bits=8, parity=None, stop=1) # init with given parameters
  uart1 = UART(1, baudrate=9600, tx=17,rx=16)# init with given baudrate
  uart1.init(9600, bits=8, parity=None, stop=1) # init with given parameters
  # Azure IoT-hub settings
  hostname = "checkinwattsiothub.azure-devices.net"
  #This needs to be the key of the "device" IoT-hub shared access policy, NOT the device
  #primary_key = "XXXXXXXXXXXXXX"
  device_id = ubinascii.hexlify(network.WLAN().config('mac'),':').decode()
  device_id = device_id.upper()
  uri = "{hostname}/devices/{device_id}".format(hostname=hostname, device_id=device_id)
  #password = "SharedAccessSignature sr=CheckinWattsHub.azure-devices.net%2Fdevices%2FB4%253AE6%253A2D%253AEB%253A64%253A6D&sig=GAJt50FAe2w7CVauKHl1yW6zzMI1UMjp2VMM9HA5AIc%3D&se=1605029220"
  username_fmt = "{}/{}/?api-version=2018-06-30"
  key="XxXK7Pun5XQa/NqUsGBmXBKI4euLUcU/72bjxuPr+jE="
  username = username_fmt.format(hostname, device_id)
  contrasena=Sas_token(uri,key)
  while True:
    if check_time_update_github(time_last_update):
      try:
        o.check_for_update_to_install_during_next_reboot()
        time_last_update=time.mktime(time.localtime())
      except:
        print("NO SE PUEDE CONECTAR PARA VER SI HAY ACTUALIZACION")
    msg_txt_formatted=Read_PZEM_and_Estruct_Message(led,uart,uart1)  
    print ("Message ready to ship to IoT Hub Azure") 
    print (msg_txt_formatted)
    iot_hub_mqttsend(device_id, hostname,username,contrasena,msg_txt_formatted) 