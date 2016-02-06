import sys
import struct

header = {}
channels = []

def hex_to_int(h1=0, h2=0, h3=0, h4=0):
	return struct.unpack('<i', bytes([h1, h2, h3, h4]))[0]

def hex_to_float(h1=0, h2=0, h3=0, h4=0):
	return struct.unpack('<f', bytes([h1, h2, h3, h4]))[0]	
	
def parse_ascii(ascii):
	global info
	global channels
	
	# Split into lines and to key - value pairs	
	lines = ascii.split('\r\n')
	rows = []
	for row in range(1, len(lines)):
		fields = lines[row].split(':')
		rows.append({'key': fields[0], 'value': ':'.join(fields[1:])})
	
	# Get header info
	index = 1
	while rows[index]['key'] != 'endheader' and index < len(rows):
		header[rows[index]['key']] = rows[index]['value']
		index += 1

	# Get channels info
	while index < len(rows):
		if rows[index]['key'] == 'beginchannel':
			channel = {}
			while rows[index]['key'] != 'endchannel' and index < len(rows):
				channel[rows[index]['key']] = rows[index]['value']
				index += 1
			channels.append(channel)

		index += 1
	
	return 0


	block_data = []
	
	points = hex_to_int(data[offset+0], data[offset+1])
	next_offset = hex_to_int(data[offset+2], data[offset+3], data[offset+4], data[offset+5])
	
	size = 5
	
	for index in range(points):
		point_offset = offset + 6 + index*size
		frames = hex_to_int(data[point_offset+0])
		value = hex_to_float(data[point_offset+1], data[point_offset+2], data[point_offset+3], data[point_offset+4])
		block_data.append({'frames':frames, 'value':value})
	
	return {'points':points, 'next_offset':next_offset, 'data':block_data}
	
def parse_channels_data():	
	for ch_index in range(len(channels)):
		channels[ch_index]['data'] = []
		total_frames = 0
		size = 5
		if 'digchannel' in channels[ch_index]:
			size = 2
			
		offset = channels[ch_index]['offset']
		while offset < len(data) and offset != 0:
			points = hex_to_int(data[offset+0], data[offset+1])
			ch_next_offset = hex_to_int(data[offset+2], data[offset+3], data[offset+4], data[offset+5])
			
			for index in range(points):
				point_offset = offset + 6 + index*size
				if size == 5:
					frames = hex_to_int(data[point_offset+0])
					value = hex_to_float(data[point_offset+1], data[point_offset+2], data[point_offset+3], data[point_offset+4])
				else:
					frames = hex_to_int(data[point_offset+0], data[point_offset+1] & ~ (1 << 6 | 1 << 7))
					value = data[point_offset+1] & (1 << 7) > 0
					
				channels[ch_index]['data'].append({'frames':frames, 'value':value})
				total_frames += frames
			
			offset = ch_next_offset
	
	return 0
	
# Load iba dat file
f = open('sample.dat', 'rb')
data = f.read()
f.close()

# Cancel if wrong file header
if data[0:4].decode('cp1251') != 'PDA2':
	print('Read failed: not a PDA2 dat file')
	exit(0)

# Read channels meta-data from ASCII part of file
start = hex_to_int(data[8], data[9], data[10], data[11])
end = data.find(b'\x65\x6E\x64\x41\x53\x43\x49\x49\x3A\x0D\x0A') + 10

parse_ascii(data[start:end+1].decode('cp1251'))

# Get binary data offset
offset = 32 # binary data are before ascii meta-data
if start == 32:
	offset = end + 1 # binary data are after ascii meta-data

# Iterate over 1000 points blocks to find offset with consistent list of channels data
ch_offsets = {}
while hex_to_int(data[offset+0], data[offset+1]) == 1000: 
	ch_offset = hex_to_int(data[offset+2], data[offset+3], data[offset+4], data[offset+5])
	if offset in ch_offsets:
		ch_offsets[ch_offset] = ch_offsets.pop(offset)
	else:
		ch_offsets[ch_offset] = offset
	offset += 5006

# Initialize channels with start offsets
for ch_index in range(len(channels)):
	ch_points = hex_to_int(data[offset+0], data[offset+1])
	ch_offset = hex_to_int(data[offset+2], data[offset+3], data[offset+4], data[offset+5])
	
	size = 5
	if 'digchannel' in channels[ch_index]:
		size = 2
		
	if offset in ch_offsets:
		channels[ch_index]['offset'] = ch_offsets[offset]
	else:
		channels[ch_index]['offset'] = offset
		
	offset += 6 + ch_points*size


# Parse data for channels
parse_channels_data()
	
exit(0)
