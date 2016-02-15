import sys
import struct
from datetime import datetime
from datetime import timedelta
import glob

class channel:
	def __init__ (self, id, name, base, scale, frame):
		self.id = id
		self.name = name
		self.base = base
		self.scale = scale
		self.frame = frame
		self.offset = 0
		self.values = []
		
		self.count = 0
		self.sum = 0
		
	def add(self, count, value):
		count *= self.scale
		while self.count + count >= self.frame:
			if self.base == 2:
				#self.values.append("{0:d}".format(round((self.sum*self.count + (self.frame - self.count)*value)/self.frame) ))
				self.values.append(round((self.sum*self.count + (self.frame - self.count)*value)/self.frame))
			else:
				#self.values.append("{0:e}".format((self.sum*self.count + (self.frame - self.count)*value)/self.frame ))
				self.values.append((self.sum*self.count + (self.frame - self.count)*value)/self.frame)

			count -= self.frame - self.count
			self.count = 0
			self.sum = 0
		
		self.count += count
		self.sum += count*value

class iba:
	def __init__(self, filename, frame):
		self.filename = filename
		self.frame = frame
		self.data = []
		self.header = {}
		self.channels = []
		
		self.parse_file()

	def hex_to_int(self, h1=0, h2=0, h3=0, h4=0):
		return struct.unpack('<i', bytes([h1, h2, h3, h4]))[0]

	def hex_to_float(self, h1=0, h2=0, h3=0, h4=0):
		return struct.unpack('<f', bytes([h1, h2, h3, h4]))[0]	
		
	def starttime(self):
		return datetime.strptime(self.header['starttime'], '%d.%m.%Y %H:%M:%S.%f')
		
	def parse_file(self):
		# Load iba dat file
		f = open(self.filename, 'rb')
		self.data = f.read()
		f.close()
		
		# Cancel if wrong file header
		if self.data[0:4].decode('cp1251') != 'PDA2':
			print('Read failed: not a PDA2 dat file')
			exit(0)

		# Read channels meta-data from ASCII part of file
		start = self.hex_to_int(self.data[8], self.data[9], self.data[10], self.data[11])
		end = self.data.find(b'\x65\x6E\x64\x41\x53\x43\x49\x49\x3A\x0D\x0A') + 10

		# Parse ASCII part of file with channels meta-data
	
		# Split into lines and to key - value pairs	
		lines = self.data[start:end+1].decode('cp1251').split('\r\n')
		rows = []
		for row in range(1, len(lines)):
			fields = lines[row].split(':')
			rows.append({'key': fields[0], 'value': ':'.join(fields[1:])})
		
		# Get header info
		index = 0
		while rows[index]['key'] != 'endheader' and index < len(rows):
			self.header[rows[index]['key']] = rows[index]['value']
			index += 1

		# Get channels info
		while index < len(rows):
			if rows[index]['key'] == 'beginchannel':
				ch = {}
				while rows[index]['key'] != 'endchannel' and index < len(rows):
					ch[rows[index]['key']] = rows[index]['value']
					index += 1
				
				id = ch['beginchannel']
				name = ch['name']
				
				if 'digchannel' in ch:
					base  = 2
				else:
					base = 5
				
				scale = int(float(ch['$PDA_Tbase'])/float(self.header['clk']))

				self.channels.append(channel(id, name, base, scale, self.frame))

			index += 1		

		# Get binary data offset
		offset = 32 # binary data are before ascii meta-data
		if start == 32:
			offset = end + 1 # binary data are after ascii meta-data

		# Iterate over 1000 points blocks to find offset with consistent list of channels data
		ch_offsets = {}
		while self.hex_to_int(self.data[offset+0], self.data[offset+1]) == 1000: 
			ch_offset = self.hex_to_int(self.data[offset+2], self.data[offset+3], self.data[offset+4], self.data[offset+5])
			if offset in ch_offsets:
				ch_offsets[ch_offset] = ch_offsets.pop(offset)
			else:
				ch_offsets[ch_offset] = offset
			offset += 5006

		# Initialize channels with start offsets
		for ch_index in range(len(self.channels)):
			ch_points = self.hex_to_int(self.data[offset+0], self.data[offset+1])
			ch_offset = self.hex_to_int(self.data[offset+2], self.data[offset+3], self.data[offset+4], self.data[offset+5])
		
	
			if offset in ch_offsets:
				self.channels[ch_index].offset = ch_offsets[offset]
			else:
				self.channels[ch_index].offset = offset
			
			offset += 6 + self.channels[ch_index].base*ch_points
			
		# Parse binary data
		for ch_index in range(len(self.channels)):
				
			offset = self.channels[ch_index].offset
			while offset < len(self.data) and offset != 0:
				points = self.hex_to_int(self.data[offset+0], self.data[offset+1])
				ch_next_offset = self.hex_to_int(self.data[offset+2], self.data[offset+3], self.data[offset+4], self.data[offset+5])
				
				for index in range(points):
					point_offset = offset + 6 + index*self.channels[ch_index].base
					if self.channels[ch_index].base == 5:
						count = self.hex_to_int(self.data[point_offset+0])
						value = self.hex_to_float(self.data[point_offset+1], self.data[point_offset+2], self.data[point_offset+3], self.data[point_offset+4])
					else:
						count = self.hex_to_int(self.data[point_offset+0], self.data[point_offset+1] & ~ (1 << 6 | 1 << 7))
						value = self.data[point_offset+1] & (1 << 7) > 0
						
					self.channels[ch_index].add(count, value)
				
				offset = ch_next_offset
	
	def get_data(self):
	
		start_time = datetime.strptime(self.header['starttime'], '%d.%m.%Y %H:%M:%S.%f')
		
		s = ''
		for t in range(int(int(self.header['frames'])/self.frame)):
			s += str(start_time + timedelta(microseconds=t*self.frame*10000)) + ';'
			for c in range(len(self.channels)):
				s += str(self.channels[c].values[t]) + ';'
			s += '\n'
		
		return s
	

# Parse dat files
csv_dir = "G:/severstal/csv/"
dat_files = glob.glob("G:/severstal/pda/2015.06/pda*.dat")

for i in range(len(dat_files)):
	t = iba(dat_files[i], 100)
	csv_filename = csv_dir + t.starttime().strftime("%Y%m%d_%H%M%S.csv")
	f = open(csv_filename, 'w')
	f.write(t.get_data())
	f.close()
	
exit(0)
