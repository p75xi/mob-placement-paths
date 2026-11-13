"""pngplot.py - tiny pure-Python PNG canvas (no PIL/numpy here): Img(w, h).px/line/disc/text/save, hue(f).
3x5 bitmap font, upper-case only."""
import zlib,struct,colorsys
F={'0':'111101101101111','1':'010110010010111','2':'111001111100111','3':'111001111001111','4':'101101111001001',
'5':'111100111001111','6':'111100111101111','7':'111001001001001','8':'111101111101111','9':'111101111001111',
'-':'000000111000000',' ':'000000000000000','.':'000000000000010',':':'000010000010000','/':'001001010100100'}
for ch,pat in {'A':'010101111101101','B':'110101110101110','C':'011100100100011','D':'110101101101110','E':'111100110100111',
'F':'111100110100100','G':'011100101101011','H':'101101111101101','I':'111010010010111','J':'001001001101010','K':'101101110101101',
'L':'100100100100111','M':'101111111101101','N':'110101101101101','O':'010101101101010','P':'110101110100100','Q':'010101101110011',
'R':'110101110101101','S':'011100010001110','T':'111010010010010','U':'101101101101111','V':'101101101101010','W':'101101111111101',
'X':'101101010101101','Y':'101101010010010','Z':'111001010100111','=':'000111000111000','+':'000010111010000','(':'010100100100010',')':'010001001001010',
'>':'100010001010100','<':'001010100010001','_':'000000000000111',',':'000000000010100'}.items(): F[ch]=pat
class Img:
    def __init__(s,w,h,bg=(255,255,255)):
        s.w,s.h=w,h; s.p=bytearray(bytes(bg)*(w*h))
    def px(s,x,y,c):
        x=int(x);y=int(y)
        if 0<=x<s.w and 0<=y<s.h: i=(y*s.w+x)*3; s.p[i:i+3]=bytes(c)
    def line(s,x0,y0,x1,y1,c,t=1):
        n=int(max(abs(x1-x0),abs(y1-y0)))+1
        for i in range(n+1):
            x=x0+(x1-x0)*i/n; y=y0+(y1-y0)*i/n
            for dx in range(t):
                for dy in range(t): s.px(x+dx,y+dy,c)
    def disc(s,x,y,r,c):
        for dx in range(-r,r+1):
            for dy in range(-r,r+1):
                if dx*dx+dy*dy<=r*r: s.px(x+dx,y+dy,c)
    def text(s,x,y,t,c,sc=1):
        for ch in str(t).upper():
            pat=F.get(ch,F[' '])
            for i,b in enumerate(pat):
                if b=='1':
                    for a in range(sc):
                        for bb in range(sc): s.px(x+(i%3)*sc+a,y+(i//3)*sc+bb,c)
            x+=4*sc
    def save(s,fn):
        raw=b''.join(b'\0'+bytes(s.p[y*s.w*3:(y+1)*s.w*3]) for y in range(s.h))
        def ck(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
        open(fn,'wb').write(b'\x89PNG\r\n\x1a\n'+ck(b'IHDR',struct.pack('>IIBBBBB',s.w,s.h,8,2,0,0,0))+ck(b'IDAT',zlib.compress(bytes(raw),6))+ck(b'IEND',b''))
def hue(f,v=0.85):
    r,g,b=colorsys.hsv_to_rgb(f*0.83,0.9,v); return (int(r*255),int(g*255),int(b*255))
