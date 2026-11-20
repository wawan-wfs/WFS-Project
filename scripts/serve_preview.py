"""Trusted bounded server executed inside isolated Docker; this script never runs on host."""
import argparse
import signal
import sys
import uvicorn


def main():
    p=argparse.ArgumentParser()
    p.add_argument('module',choices=('main','app.main','src.main','server','api.main'))
    p.add_argument('--minutes',type=int,default=15)
    args=p.parse_args()
    signal.signal(signal.SIGALRM,lambda *_:sys.exit(0))
    signal.alarm(min(30,max(1,args.minutes))*60)
    uvicorn.run(args.module+':app',host='0.0.0.0',port=8000,log_level='warning',access_log=False)


if __name__=='__main__':main()
