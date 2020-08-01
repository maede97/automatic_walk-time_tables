import math
from datetime import timedelta, datetime
from io import BytesIO

import gpxpy.gpx
import matplotlib.pyplot as plt
import numpy as np
import requests
from PIL import Image, ImageDraw

from calculations import calcTime
from find_name import find_name
from find_walk_table_points import find_points, prepare_for_plot
from transformation import GPSConverter


# creates a plot of the raw data points overlayed with the calculated way points
def create_plot(raw_data_points, way_points, file_name):
    # plot heights of exported data from SchweizMobil
    distances, heights = prepare_for_plot(raw_data_points)
    plt.plot(distances, heights, label='Wanderweg')

    # resize plot area
    additional_space = math.log(max(heights) - min(heights)) * 25
    plt.ylim(ymax=max(heights) + additional_space, ymin=min(heights) - additional_space)

    # add way_points to plot
    # plt.scatter([dist[0] for dist in temp_points], [height[1].elevation for height in temp_points], c='gray', )
    plt.scatter([dist[0] for dist in way_points], [height[1].elevation for height in way_points], c='orange', )
    plt.plot([dist[0] for dist in way_points], [height[1].elevation for height in way_points],
             label='Marschzeittabelle')

    # labels
    plt.ylabel('Höhe [m ü. M.]')
    plt.xlabel('Distanz [km]')
    plt.title('Höhenprofil', fontsize=20)
    plt.legend(loc='upper right', frameon=False)

    # Grid
    plt.grid(color='gray', linestyle='dashed', linewidth=0.5)

    # show the plot and save image
    plt.savefig('imgs/' + file_name, dpi=300)
    plt.show()


# creates the walk table and print it on the console
def create_walk_table(time_stamp, speed):
    oldPoint = None
    time = 0

    print('                                                     Geschwindikeit: ', speed, 'km/h')
    print()
    print('Distanz Höhe           Zeit   Uhrzeit     Ort (Koordinaten und Namen)')

    # get Infos points
    for point in way_points_walk_table:

        # convert Coordinates to LV03
        converter = GPSConverter()
        wgs84 = [point[1].latitude, point[1].longitude, point[1].elevation]
        lv03 = converter.WGS84toLV03(wgs84[0], wgs84[1], wgs84[2])
        lv03 = np.round(lv03)

        # calc time
        deltaTime = 0.0
        if oldPoint is not None:
            deltaTime = calcTime(point[1].elevation - oldPoint[1].elevation, abs(oldPoint[0] - point[0]), speed)
        time += deltaTime

        time_stamp = time_stamp + timedelta(hours=deltaTime)

        # print infos
        print(
            round(abs((oldPoint[0] if oldPoint is not None else 0.0) - point[0]), 1), 'km ',
            int(lv03[2]), 'm ü. M.  ',
            round(deltaTime, 1), 'h ',
            time_stamp.strftime('%H:%M'), 'Uhr  ',
            (int(lv03[0]), int(lv03[1])), find_name((lv03[0] + 2_000_000, lv03[1] + 1_000_000), 75))

        oldPoint = point

    print('--- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---')
    print(round(total_distance, 1), 'km', '', round(time, 1), 'h')
    print('=== === === === === === === === === === === === === === === === === === ===')
    print()
    print()


# creates a map snippet of the point at the given coord (WGS84 format) and and mark it
# saves the imag in the folder 'imgs/'

def create_map_snippet(coord, point_index):
    # convert Coordinates to LV03
    converter = GPSConverter()
    wgs84 = [coord.latitude, coord.longitude, coord.elevation]
    lv03 = converter.WGS84toLV03(wgs84[0], wgs84[1], wgs84[2])
    lv03 = np.round(lv03)

    # zoom level of the map snippets (a value form 0 to 12)
    zoom_level = 6

    # define constants
    tile_size = [64000, 25600, 12800, 5120, 2560, 1280, 640, 512, 384, 256, 128, 64, 25.6]
    zoom_levels = [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]

    # calc the number of the centered tile
    x_tile = math.floor((lv03[0] - 420_000) / tile_size[zoom_level])
    y_tile = math.floor((350_000 - lv03[1]) / tile_size[zoom_level])

    # creates the urls of the image tiles as a 3x3 grid around the centered tile
    base_url = 'https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/2056/' + str(
        zoom_levels[zoom_level]) + '/'
    urls = [base_url + str(x_tile - 1) + '/' + str(y_tile - 1) + '.jpeg',
            base_url + str(x_tile - 1) + '/' + str(y_tile) + '.jpeg',
            base_url + str(x_tile - 1) + '/' + str(y_tile + 1) + '.jpeg',
            base_url + str(x_tile) + '/' + str(y_tile - 1) + '.jpeg',
            base_url + str(x_tile) + '/' + str(y_tile) + '.jpeg',
            base_url + str(x_tile) + '/' + str(y_tile + 1) + '.jpeg',
            base_url + str(x_tile + 1) + '/' + str(y_tile - 1) + '.jpeg',
            base_url + str(x_tile + 1) + '/' + str(y_tile) + '.jpeg',
            base_url + str(x_tile + 1) + '/' + str(y_tile + 1) + '.jpeg']

    # load tiles and combine map parts
    card_snippet_as_image = Image.new("RGB", (254 * 3, 254 * 3))
    for index, url in enumerate(urls):
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        img.thumbnail((254, 254), Image.ANTIALIAS)
        x = index // 3 * 254
        y = index % 3 * 254
        w, h = img.size
        card_snippet_as_image.paste(img, (x, y, x + w, y + h))

    # calc the coords in respect to the image pixels
    img_x = 256.0 + ((lv03[0] - 420_000) % tile_size[zoom_level]) / (tile_size[zoom_level] / 254.0)
    img_y = 256.0 + ((350_000 - lv03[1]) % tile_size[zoom_level]) / (tile_size[zoom_level] / 254.0)
    circle_coords = (img_x - 18, img_y - 18, img_x + 18, img_y + 18)

    # mark point on the map
    draw = ImageDraw.Draw(card_snippet_as_image)
    draw.ellipse(circle_coords, outline=(255, 0, 0), width=5)

    # saves the image as '.jpg'
    card_snippet_as_image.save('imgs/' + str(point_index) + '_' + str(int(lv03[0])) + '_' + str(int(lv03[1])) + '.jpg')


########################################################################################################################
########################################################################################################################
########################################################################################################################


# Open GPX-File with the way-points
gpx_file = open('./testWalks/hikesommerlager2020tag2.gpx', 'r')
gpx = gpxpy.parse(gpx_file)

# define the departure time of the hike
start_time = datetime(year=2020, month=8, day=10, hour=10, minute=00)

# get Meta-Data
name = gpx.tracks[0].name

# calc Points for walk table
total_distance, temp_points, way_points_walk_table = find_points(gpx)
create_plot(gpx, way_points_walk_table,  file_name=name + '.png')

# prints the walk table and the associated timestamps / meta infos
create_walk_table(start_time, 4.2)

# create ma snippets of each way point
for i, point in enumerate(way_points_walk_table):
    create_map_snippet(point[1], i)