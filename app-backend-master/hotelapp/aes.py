from Crypto.Cipher import AES
import base64


class AEScoder():
    def __init__(self):
        self.__encryptKey = "iEpSxImA1vpMUAAbsjJWug=="
        self.__key = base64.b64decode(self.__encryptKey)

    # AES加密
    def encrypt(self, data):
        BS = 16
        pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        cipher = AES.new(self.__key, AES.MODE_ECB)
        padData=pad(data)
        encrData = cipher.encrypt(padData.encode('utf-8'))
        encrData = base64.b64encode(encrData)
        return encrData.decode('utf-8')

    # AES解密
    def decrypt(self, encrData):
        try:
            encrData = encrData.encode('utf-8')
            encrData = base64.b64decode(encrData)
            unpad = lambda s: s[0:-s[len(s)-1]]
            # unpad = lambda s: s[0:-s[-1]]
            cipher = AES.new(self.__key, AES.MODE_ECB)
            decrData = unpad(cipher.decrypt(encrData))
        except:
            return None
        return decrData.decode('utf-8')