#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# switchscreen - Check screens each second and change xrandr configuration if needed
# (c) Régis FLORET 2011 <regis.floret@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
    switchscreen [OPTION]

    TODO:
        --initiate-config
        --stop
        --restart
        SwitchScreen.Daemonize routine
"""

__author__ = u"Régis FLORET"
__copyright__ = u"Copyright (c) Régis FLORET 2011"
__version__ = "0.1"

import os
import sys
import time
import subprocess
import shlex
import signal
import optparse
import logging

# Create the logger instance
log_handler = logging.getLogger('switchscreen')

# Default log file name
DEFAULT_LOG = os.path.expanduser("~/.switchscreen.log")

class ConfigFileNotFound(Exception):
    """ Raised when the configuration file was not found """
    pass

class ConfigSyntaxError(SyntaxError):
    """ Raised when the configuration file is not well written """
    pass

class Configuration(object):
    """ Handle configuration including command line option if any """
    __config = None
    @classmethod
    def getConfig(cls):
        """ Get the configuration.
        You should always use this method to get configuration object.
        It's a sinple way for lazy programmers like me.
        """
        if cls.__config is None:
            cls.__config = Configuration()
        return cls.__config

    def __init__(self):
        """ Contructor. Create minimal config dict """
        self.__config_dict = {'configuration': {'config_path': [] }}
        self.default_config = ''
        
    def __str__(self):
        """ Return the configuration dict as string (usefull for debugging) """
        return self.__config_dict.__str__()
        
    def show_config(self):
        """ Return a well formated string for configuration """
        str = "Configuration for switchscreen:\n"
        str += "\tRun as daemon      : %s\n" % self.__config_dict['configuration']['daemonize']
        str += "\tRoot path          : %s\n" % self.__config_dict['configuration']['root_path']
        str += "\tConfiguration path : %s\n" % self.__config_dict['configuration']['config_path']
        str += "\tTime to wait       : %d secs\n" % self.__config_dict['configuration']['time_to_wait']
        str += "\tumask              : %d\n" % self.__config_dict['configuration']['umask']
        
        str += "\nScreens:\n"
        for screen in self.__config_dict.get('screen', []):
            str += "\tNumber of screen: %d\n" % screen
            dico = self.__config_dict['screen'][screen]
            for scr in dico:
                str += "\t\tName : %s\n" % scr
                if dico[scr].has_key('main'):
                    str += "\t\t\tMain    : %s\n" % dico[scr].get('main', False)
                if dico[scr].has_key('display'):
                    str += "\t\t\tDisplay : %s\n" % dico[scr].get('display', False)
                if dico[scr].has_key('pos'):
                    str += "\t\t\tPos     : %s\n" % dico[scr].get('pos', "Not set")
                if dico[scr].has_key('mode'):
                    str += "\t\t\tMode    : %s\n" % dico[scr].get('mode', "Not set")
                if dico[scr].has_key('refresh'):
                    str += "\t\t\tRefresh : %s\n" % dico[scr].get('refresh', "Not set")
            str += "\n"
        return str

    def read_config_file(self):
        """ Read the configuration file """
        config_found = False
        for path in self.__config_dict['configuration']['config_path']:
            
            path = os.path.join(os.path.expanduser(path), ".switchscreenrc")
            if os.path.isfile(path):
                config_found = True
                break
            
        if not config_found:
            raise ConfigFileNotFound("No configuration file found")
        
        try:
            # Keep config_path
            config_path = self.__config_dict['configuration']['config_path']
            self.__config_dict.update(eval(open(path, 'r').read()))
            self.__config_dict['configuration']['config_path'] += config_path

            #if self.__config_dict['configuration'].has_key('default'):
            #    print self.get_config_for(self.__config_dict['configuration']['default'])
            
            self.set_log_file(self.__config_dict['configuration']['logfile'])
            
        except SyntaxError as e:
            raise ConfigSyntaxError("configuration file not well written: %s" %e)
        
    def set_time_to_wait(self, ttw):
        """ Set the time between two test.
        ttw may be a double like 0.5 """
        self.__config_dict['configuration']['time_to_wait'] = ttw
        
    def get_time_to_wait(self):
        return self.__config_dict['configuration']['time_to_wait']
    
    def set_root_path(self, path):
        """ The the rout path for daemon """
        self.__config_dict['configuration']['root_path'] = path
        
    def get_root_path(self):
        return os.path.expanduser(self.__config_dict['configuration']['root_path'])

    def set_daemonize(self, daemonize):
        """ Set if the program should run as daemon """
        self.__config_dict['configuration']['daemonize'] = daemonize
        
    def get_daemonize(self):
        return self.__config_dict['configuration']['daemonize']
        
    def set_log_file(self, logfile):
        """ Set the log file """
        self.__config_dict['configuration']['logfile'] = os.path.expanduser(logfile)
        
    def get_log_file(self):
        """ Return the log file name """
        return self.__config_dict['configuration']['logfile']

    def add_config_path(self, path):
        """ Add a configuration path """
        self.__config_dict['configuration']['config_path'].append(path)
        
    def have_config_for(self, screencount):
        """ Test if the configuration can handle the number of screen count """
        return self.__config_dict['screen'].has_key(screencount)
        
    def get_config_for(self, screencount):
        """ Return the configuration for the screen count """
        return self.__config_dict['screen'][screencount]
        
    def set_umask(self, mask):
        """ Set the umask for the daemon """
        self.__config_dict['configuration']['umask'] = mask
        
    def get_umask(self):
        """ Return the umask for the daemon """
        return self.__config_dict['configuration']['umask']
        
        
class SwitchScreen(object):
    """ """
    def __init__(self):
        """ ctor """
        self.logfilename = None
        self.stop = False
        self.install_signal()
                
        str = 'Starting switchscreen as %s'
        if Configuration.getConfig().get_daemonize() == True:
            logging.info(str % 'daemon')
        else:
            logging.info(str % 'console program.')

    def install_signal(self):
        """ Install signal handling """
        signal.signal(signal.SIGINT, self.signal_int)
        signal.signal(signal.SIGHUP, self.signal_hup)
        
    def signal_int(self, s, f):
        """ Interruption required. Exit gently """
        self.stop = True
        
    def signal_hup(self, s, f):
        """ Reload configuration """
        Configuration.getConfig().read_config_file()
                
    def to_command(self, dico):
        """ Return a list of list of command from dictionnary """
        cmd = ""
        cmdlist = []
        
        for screen in dico.keys():
            cmd = "xrandr --output %s" % screen
            if dico[screen].has_key('display'):
                if not dico[screen]['display']:
                    # Off screen disable all other options
                    cmd = "xrandr --output %s --off" % screen
                    cmdlist.append(cmd)
                else:
                    if dico[screen].has_key('pos'):
                        cmd += " --pos %s" % dico[screen]['pos']
                    if dico[screen].has_key('mode'):
                        cmd += " --mode %s" % dico[screen]['mode']
                    if dico[screen].has_key('refresh'):
                        cmd += ' --refresh %s' % dico[screen]['refresh']
                    if dico[screen].has_key('main'):
                        if dico[screen]['main']:
                            cmd += " --primary"
                    cmdlist.append(cmd)
        commands = []
        for cmd in cmdlist:
            commands.append(shlex.split(cmd))
            
        for command in cmdlist:
            logging.info("Shell command : %s" % command)
            
        return commands
        
    def switch_screen(self, screen_count, execute=True):
        """ switch between configurations """
        logging.info("Switching screen")
        commands = None
        config = Configuration.getConfig()
        if config.have_config_for(screen_count):
            commands = self.to_command(config.get_config_for(screen_count))
        else:
            # Todo : raise exception
            #print "No configuration for this"
            return
        
        # Wait to allow xrandr to find plugged devices
        time.sleep(0.5) 
        for cmd in commands:
            if execute == False:
                # Simulation
                print " ".join(cmd)
            else:
                subprocess.Popen(cmd)

    def get_screen_count(self, output):
        """ Parse xrandr output and get screens connected count """
        screen_count = 0
        for line in output.split('\n'):
            if len(line.strip()) == 0:
                continue
            if line[0] != ' ' and not line.startswith("Screen") and not "disconnect" in line:
                screen_count += 1
        return screen_count

    def check_screens(self):
        """ start sub process to call xrandr """
        proc = subprocess.Popen(["xrandr",], stdout= subprocess.PIPE)
        out,err = proc.communicate()
        return self.get_screen_count(out)

    def daemonize(self):
        """ Do a fork fork to run the program as a daemon taking care of the
        configuration file """
        if Configuration.getConfig().get_daemonize():
            try:
                pid = os.fork()
            except OSError as e:
                logging.error(e)
                sys.exit(1)
            
            if pid == 0:
                os.setsid()
                try:
                    pid = os.fork()
                except OSError as e:
                    logging.error(e.strerror)
                    sys.exit(1)

                if pid == 0:
                    os.chdir(Configuration.getConfig().get_root_path())
                    os.umask(Configuration.getConfig().get_umask())
                else:
                    os._exit(0)
            else:
                os._exit(0)
                
            # Close std{out,err,in}
            os.open(os.devnull, os.O_RDWR)
            os.dup2(0, 1)
            os.dup2(0, 2)

    def main_loop(self):
        """ Process main loop """
        #try:
        last_scr_count = self.check_screens()
        while not self.stop:
            current_scr_count = self.check_screens()
            if current_scr_count != last_scr_count:
                last_scr_count = current_scr_count
                self.switch_screen(current_scr_count)
            time.sleep(Configuration.getConfig().get_time_to_wait())
        #except Exception as e:
        #    """ Crash restore the default configuration """
        #    logging.error("Crash. Restore the default configuration.")
        #    command = Configuration.getConfig().get_default_config()
        #    subprocess.Popen(self.to_command(command))
            
    def set_log_file(self, logfilename):
        """ Set the log file name """
        self.logfilename = logfilename

def main():
    """ The main loop for command line program """
    try:
        config = Configuration.getConfig()
        config.add_config_path('.')
        config.add_config_path('~')
        config.read_config_file()
    except ConfigFileNotFound as e:
        sys.exit("Error : %s. Create a configuration file and restart the program." %e)
    except ConfigSyntaxError as e:
        sys.exit(e)
        
    #  parse command line arguments
    parser = optparse.OptionParser(__doc__, version=__version__)
    parser.add_option("-n", "--no-daemon",
                      action="store_false", dest="daemon",
                      default=True,
                      help="Don't run the program as daemon")
    parser.add_option("-t", "--time-to-wait",
                      dest="time_to_wait", type="float", default=1,
                      help="Set the pause between each verificaton (may be a float)",
                      metavar="seconds")
    parser.add_option("-r", "--root-path",
                      dest="root_path", type="string",
                      help="Set the daemon root path",
                      metavar="rootpath")
    parser.add_option("-p", "--config-path", dest="config_path",
                      type="string",
                      help="Set the configuration file path. May be a string separated with ':'",
                      metavar="configdir")
    parser.add_option("-l", "--log-file", dest="log_file",
                      type="string", help="Set the log file name",
                      metavar="logfile")
    #parser.add_option('-s', '--stop', dest="stop_daemon",
    #                  action="store_true",
    #                  help="Stop daemon")
    #parser.add_option('-u', '--restart', dest="restart_daemon",
    #                  action="store_true",
    #                  help="Restart daemon")
    parser.add_option('-c', '--show-config', dest='show_conf',
                      action="store_true",
                      help="Show configuration")
    #parser.add_option('-i', '--initiate-config', dest='initiate',
    #                  action='store_true',
    #                  help='Display the computed configuration file')
    parser.add_option('-m', '--simulate', dest='simulate',
                      type="int", default=0, action="store",
                      metavar="number-of-screen",
                      help="Process a simulation and display xrandr command line (Debug purpose)")
    #parser.add_option('-a', '--alive', dest="alive", action="store_true",
    #                  help="Test if a switchscreen program is running yet")
    
    options,args = parser.parse_args()
    
    config.set_time_to_wait(options.time_to_wait)
    config.set_daemonize(options.daemon)
    
    if options.root_path is not None:
        config.set_root_path(options.root_path)
    
    if options.config_path is not None:
        [config.add_config_path(p) for p in options.config_path.split(":")]
    
    if options.log_file:
        config.set_log_file(options.log_file)
        
    if options.show_conf:
        print config.show_config()
        sys.exit()
    
    if options.stop_daemon == True:
        sys.exit('--stop option is TODO. Use SIGINT or SIGKILL instead')
    
    if options.restart_daemon == True:
        sys.exit('--restart option is TODO. Use SIGHUP instead')
                
    switch = SwitchScreen()
    if options.simulate > 0:
        switch.switch_screen(options.simulate, False)
        sys.exit()
    switch.daemonize()
    switch.main_loop()
        
if __name__ == '__main__':
    main()