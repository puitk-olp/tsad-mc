#! /usr/bin/python3

import argparse
import json
import yaml
import subprocess

LOCAL_DIR = '/app/FFL/code/pablo'
COMMAND   = ['docker','run','--rm', '-v','/vol/FFL:/app/FFL']


def make_docker_command(**params):
    
    command = COMMAND

    cpu_limit = params.get('docker_cpu_limit',None)
    if cpu_limit == '':
        cpu_limit = None
    if cpu_limit != None:
        command.append("--cpu={}".format(cpu_limit))


    ram_limit = params.get('docker_ram_limit',None)
    if ram_limit == '':
        ram_limit = None
    if ram_limit != None:
        command.append("-m")
        command.append("{}".format(ram_limit))

    swap_limit = params.get('docker_swap_limit',None)
    if swap_limit == '':
        swap_limit = None
    if swap_limit!= None:
        command.append("--memory-swap")
        command.append("{}".format(swap_limit))

    time_limit = params.get('docker_time_limit',None)
    if time_limit == '':
        time_limit = None
    if time_limit != None:
        command.append("--stop-timeout")
        command.append("{}".format(time_limit))


    # add the end of the command
    command.append("{}".format(params['docker_image']))
    command.append("python")
    command.append("{}/Unit_Pipeline.py".format(LOCAL_DIR))
    command.append("--config")
    command.append("{}/{}".format(LOCAL_DIR,params['config_file']))
    return(command)
    
def run_command(command): 
    try:
        result = subprocess.run(command,capture_output=True, text=True)
    except:
        raise Exception("Something went wrong. The docker process failed")
        
    return(result)

if __name__ == '__main__':
    ## ArgumentParser
    parser = argparse.ArgumentParser(description='Running TSB-AD')
    parser.add_argument('--config',type=str,default=None)
    args = parser.parse_args()
   
    with open(args.config) as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
    config['config_file']=args.config
    command = make_docker_command(**config)
    print(command)
    result = run_command(command)
    print(result)

