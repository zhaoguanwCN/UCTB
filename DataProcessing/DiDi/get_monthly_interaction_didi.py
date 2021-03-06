import os
import time
import json
import argparse

from dateutil.parser import parse
from multi_threads import multiple_process
from data_config import *
from local_path import *

params = argparse.ArgumentParser()
params.add_argument('--data', default='DiDi', type=str)
params.add_argument('--city', default='Xian', type=str)
params.add_argument('--jobs', default=8, type=int)

args = params.parse_args()

city_config = eval('%s_%s_DataConfig()' % (args.data, args.city))
final_file_name = '%s_%s_Monthly_Interaction.npy' % (args.data, args.city)

city_config.time_fitness = (city_config.time_fitness / 60) * 24 * 30


def get_timedelta_minutes(start, end):
    if type(start) == str:
        start = parse(start)
    if type(end) == str:
        end = parse(end)
    timedelta = end - start
    return timedelta.days * 24 * 60 + int(timedelta.seconds / 60)


# multiple threads

# 1 distribute list
distributeList = city_config.file_list

# 2 partition function
partitionFunc = lambda dtList, i, n_job: [dtList[e] for e in range(len(dtList)) if e % n_job == i]

# 3 n_jobs
n_jobs = args.jobs


# 4 reduce function
def reduceFunction(a, b):
    return a + b


# 5 task function
def task(ShareQueue, Locker, distributedList, parameterList):

    num_time_slots = int(get_timedelta_minutes(city_config.time_range[0], city_config.time_range[1]) / city_config.time_fitness)

    data_array = np.zeros([num_time_slots, len(city_config.stations_ordered), len(city_config.stations_ordered)], dtype=np.int32)

    for file in distributedList:

        print(file)

        with open(os.path.join(city_config.raw_data_path, file), 'r', encoding='utf-8') as f:
            data = json.load(f)

        # start time : [1]
        # start (lat, lng) : [5, 6]

        # end time : [2]
        # end (lat, lng) : [9, 10]

        for order_id in data:

            record = data[order_id]

            if len(record) > 2:
                print(record)
                continue

            start_record_index = 0 if record[0][0] == 0 else 1

            start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record[start_record_index][city_config.file_col_index['time']]))
            start_lat = record[start_record_index][city_config.file_col_index['lat']]
            start_lng = record[start_record_index][city_config.file_col_index['lng']]

            # end_time = record[1 - start_record_index][city_config.file_col_index['time']]
            end_lat = record[1 - start_record_index][city_config.file_col_index['lat']]
            end_lng = record[1 - start_record_index][city_config.file_col_index['lng']]

            start_lat_index, start_lng_index = city_config.grid_config.get_lat_lng_index(start_lat, start_lng)
            end_lat_index, end_lng_index = city_config.grid_config.get_lat_lng_index(end_lat, end_lng)

            if 0 <= start_lat_index < city_config.grid_height and 0 <= start_lng_index < city_config.grid_width and \
               0 <= end_lat_index < city_config.grid_height and 0 <= end_lng_index < city_config.grid_width:

                time_index = int(get_timedelta_minutes(city_config.time_range[0], start_time) / city_config.time_fitness)

                if 0 <= time_index < num_time_slots:
                    data_array[time_index,
                               start_lat_index*city_config.grid_width+start_lng_index,
                               end_lat_index*city_config.grid_width+end_lng_index] += 1

    print('Process Finish')
    Locker.acquire()
    ShareQueue.put(data_array)
    Locker.release()


# 6 shared parameters
parameterList = []

if __name__ == '__main__':
    data_result = multiple_process(
        distribute_list=distributeList,
        partition_func=partitionFunc,
        task_func=task,
        n_jobs=n_jobs,
        reduce_func=reduceFunction,
        parameters=parameterList
    )

    np.save(os.path.join(didi_data_path, final_file_name), data_result, allow_pickle=True)