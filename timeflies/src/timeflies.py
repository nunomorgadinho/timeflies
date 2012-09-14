#!/usr/bin/python3

version = '0.1'

cpyrght = \
'''
  TimeFlies v. {0:s} is a work log and task tree processor.
    
  Copyright (C) 2012 Joerg Bullmann (jb@heilancoo.net)

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>. 
'''

from datetime import date
import re
import weakref
import sys
import getopt

def makeDate(dstr):
    datecomps = dstr.split('-')
    return date(int(datecomps[0]), int(datecomps[1]), int(datecomps[2]))

def isWeekend(d):
    return d.isoweekday() == 6 or d.isoweekday() == 7

def formatTimeVal(val, what):
    if val == 0.0:
        return '--.-- ' + what
    else:
        return '{0:5.2f} '.format(val) + what

class AllFilter:
    def passes(self, day):
        return True
    
class MonthFilter:
    def __init__(self, year, month):
        self.year = year
        self.month = month
    
    def passes(self, day):
        return day.date.year == self.year and day.date.month == self.month
        

class Node:
    def __init__(self):
        self.parent = None
        self.children = None
        self.childrenByName = None

    def addChild(self, node):
        if self.childrenByName == None:
            self.children = []
            self.childrenByName = {}
        
        name = node.getName()
        
        if name in self.childrenByName:
            idx = self.childrenByName[name]
            self.children[idx].parent = None
            self.children[idx] = node
        else:
            idx = len(self.children)
            self.children.append(node)
            self.childrenByName[name] = idx
            
        node.parent = weakref.ref(self)
    
    def hasChild(self, chld):
        if self.childrenByName == None:
            return False
        elif isinstance(chld, int):
            return 0 <= chld and chld < len(self.children)
        else:
            return chld in self.childrenByName
    
    def getChild(self, chld):
        if not self.hasChild(chld):
            return None
        elif isinstance(chld, int):
            return self.children[chld]
        else:
            return self.children[self.childrenByName[chld]]
    
    def getNode(self, pathstr, create=False):
        path = pathstr.split('.')
        n = self
        for c in path:
            if n.hasChild(c):
                n = n.getChild(c)
            else:
                if not create:
                    return None
                else:
                    newnode = self.createNode(c)
                    n.addChild(newnode)
                    n = newnode
        return n

    def dump(self, options, indent=''):
        self.dumpNode(options, indent)
        if self.children != None:
            indent += options['indent']
            for c in self.children:
                c.dump(options, indent)

def dumpActivities(activities, indent, options):
        indent += options['indent']
        
        for a in activities:
            comment = (', ' + a.description) if a.description != None else ''
            print(indent + '@ ' + str(a.day().date) + ' ' + str(a.duration) + comment)

class ValueNode(Node):
    def __init__(self, task, value=None):
        Node.__init__(self)
        self.value = value
        self.task = task
        self.activities = []
    
    def getName(self):
        return self.task.name
    
    def addActivity(self, activity):
        self.activities.append(activity)

    def dumpNode(self, options, indent):
        desc = self.task.description
        descetc = (' -- ' + desc) if desc != None else ''
        print('{1:s}{0:6.2f} : {2:s}{3:s}'.format(self.value, indent, self.getName(), descetc, ))
        
        if 'activities' in options:
            dumpActivities(self.activities, '         ' + indent, options)
 
class Task(Node):
    def __init__(self, name, desc=None, effort=0):
        Node.__init__(self)
        self.name = name
        self.description = desc
        self.effort = int(effort)
        self.activities = []
    
    def createNode(self, name):
        return Task(name)
    
    def getName(self):
        return self.name
    
    def calcEffort(self):
        e = self.effort
        for s in self.children:
            e += s.calcEffort()
        return e
    
    def calcActivity(self, dayfilter):
        res = ValueNode(self)
        totals = 0.0;
        for a in self.activities:
            if dayfilter.passes(a.day()):
                totals += a.duration
                res.addActivity(a)

        if totals != 0.0 and self.children != None:
            res.addChild(ValueNode('--self--', totals))
        
        if self.children != None:
            for s in self.children:
                c = s.calcActivity(dayfilter)
                if c.value != 0.0:
                    totals += c.value
                    res.addChild(c)
        
        res.value = totals
            
        return res
        
    def addActivity(self, activity):
        self.activities.append(activity)
        activity.task = weakref.ref(self)

    def dumpNode(self, options, indent):
        desc = (' -- ' + self.description) if self.description != None else ''        
        print(indent + self.name + desc)
        
        if 'activities' in options:
            dumpActivities(self.activities, indent, options)

class Activity:
    def __init__(self, duration, description):
        self.day = None
        self.task = None
        self.duration = float(duration)
        self.description = description
        
class Day:
    """A Day object represents a day of work. It has a date,
    hour information and comment information attached to it."""
    def __init__(self, dt):
        if isinstance(dt, str):
            self.date = makeDate(dt)
        elif isinstance(dt, date):
            self.date = dt
        else:
            self.date = None
        self.directives = None
        self.start = 0
        self.stop = 0
        self.off = 0
        self.ill = 0
        self.leave = 0
        self.phol = False
        self.comments = []
        self.activities = []
        
    def addDirective(self, d):
        if self.directives == None:
            self.directives = [ d ]
        else:
            self.directives.append(d)
    
    def addActivity(self, activity):
        self.activities.append(activity)
        activity.day = weakref.ref(self)
        
    def addComment(self, comment):
        self.comments.append(comment)

    def addOff(self, off):
        self.off += off

    def setPhol(self, phol):
        self.phol = phol

    def addLeave(self, leave):
        self.leave += leave

    def addIll(self, ill):
        self.ill = ill

    def setHours(self, start, stop):
        self.start = start
        self.stop = stop

    def calcActivity(self):
        totals = 0.0
        for a in self.activities:
            totals += a.duration
        return totals
        
    def calcBalance(self):
        return self.calcWorked() + self.ill + self.leave

    def calcWorked(self):
        return self.stop - self.start - self.off
    
    def calcRequired(self):
        if self.phol or isWeekend(self.date):
            return 0.0
        else:
            return 8.0
    
    def dump(self):
        print(self.date.strftime('%Y-%m-%d, %a: ') + \
              formatTimeVal(self.calcWorked(), "worked") + ', ' +\
              formatTimeVal(self.leave, "leave") + ', ' +\
              formatTimeVal(self.ill, "ill"))

        
class Directive:
    def __init__(self):
        self.reset = False
        self.leave = None
        self.must = None
        self.have = None

    def setLeave(self, leave):
        self.leave = leave
        return self
    
    def setMust(self, must):
        self.must = must
        return self
    
    def setHave(self, have):
        self.have = have
        return self
    
    def setReset(self):
        self.reset = True
        return self

class Universe:
    def __init__(self):
        self.days = {}
        self.taskroot = Task("ALL")
        
    def getChronoDays(self):
        return sorted(self.days.values(), key = lambda day: day.date)
    
class TaskLineBookmark:
    def __init__(self, task, indent, parent=None):
        self.indent = indent
        self.task = task
        self.parent = parent

class Reader:
    def __init__(self, uni):
        self.universe = uni
        self.inputfile = None
        self.linecount = 0
        self.currentday = None

    def read(self, inputfile):
        self.inputfile = inputfile
        f = open(inputfile)
        self.linecount = 0
        self.currentday = None
        self.resetTaskStack()
        
        for line in f:
            self.linecount += 1
            line = re.sub(" *#.*", "", line).rstrip()
            
            if line == '':
                self.resetTaskStack()
            elif self.inTaskDefinition():
                self.processTask(line)
            elif line.startswith('task '):
                self.processTask(line[5:].strip())
            else:
                self.resetTaskStack()
                    
                if line.startswith('- '):
                    self.processActivity(line[2:].strip())
                elif line.startswith('-- '):
                    self.processComment(line[3:].strip())
                elif line.startswith('todo '):
                    if not self.currentday == None:
                        self.msg('WARNING: TO DO item found beyond the beginning of the file')
                    else:
                        self.msg('TO DO: ' + line[5:].strip())
                elif line.strip() != '':
                    self.processInstructions(line)
        f.close()
        
    def msg(self, text):
        print(self.inputfile + ':' + str(self.linecount) + ': ' + text)
        
    def resetTaskStack(self):
        self.taskstack = TaskLineBookmark(self.universe.taskroot, -1)

    def inTaskDefinition(self):
        return self.universe.taskroot != self.taskstack.task
    
    #   name.of.the.task [params ...], description
    def processTask(self, line):
        items = line.split(',', 1)
        spec = items[0].strip().split(' ')
        fullname = spec[0]
                
        indent = len(line) - len(line.lstrip())
        
        while indent <= self.taskstack.indent:
            self.taskstack = self.taskstack.parent
        
        task = self.taskstack.task.getNode(fullname, create=True)
        
        if len(spec) > 1: # effort
            task.effort = spec[1]
            
        if len(items) == 2: # description
            task.description = items[1].strip()
        
        self.taskstack = TaskLineBookmark(task, indent, self.taskstack)
        
    def processActivity(self, line):
        comps = line.split(',', 1)
        args = comps[0].strip().split(' ')
        if len(args) < 2:
            self.msg('an activity must have a task and a duration.')
        else:
            taskname = args[0]
            duration = args[1]
            if len(comps) == 2:
                desc = comps[1].strip()
            else:
                desc = None

            try:
                activity = Activity(duration, desc)
                task = self.universe.taskroot.getNode(taskname)
                if task == None:
                    self.msg('invalid activity task ' + taskname
                             + ' on day ' + str(self.currentday.date))
                else:
                    task.addActivity(activity)
                    self.currentday.addActivity(activity)
            except ValueError:
                self.msg('invalid activity duration ' + duration + '.')
            
        
    def processComment(self, comment):
        self.currentday.addComment(comment)

    def processInstructions(self, line):
        morsels = line.split(',')
        for mors in morsels:
            self.processInstruction(mors.strip())

    def addLeave(self, start, end, where):
        st = makeDate(start)
        end = makeDate(end)

        d = st.toordinal()
        end = end.toordinal()

        while d <= end:
            dt = date.fromordinal(d)

            if not isWeekend(dt):
                self.newDay(str(dt))
                self.currentday.addLeave(8.0)
                self.currentday.addComment('leave: ' + where)

            d = d + 1

    def newDay(self, datestring):
        if datestring in self.universe.days:
            self.currentday = self.universe.days[datestring]
        else:
            self.currentday = Day(datestring)
            self.universe.days[datestring] = self.currentday

    def processInstruction(self, argliststring):
        arglist = argliststring.split(' ')
        instr = arglist[0]
        args = arglist[1:]

        if instr == 'day':
            self.newDay(args[0])
            return
        
        if instr == 'leave' and len(args) == 3:
            self.addLeave(args[0], args[1], args[2])
            return
        
        if self.currentday == None:
            self.msg('No current day for instruction <' + argliststring + '>.')
            return
        
        if instr == 'reset':
            self.currentday.addDirective(Directive().setReset())
        elif instr == 'add-leave':
            self.currentday.addDirective(Directive().setLeave(float(args[0])))
        elif instr == 'balance-must':
            self.currentday.addDirective(Directive().setMust(float(args[0])))
        elif instr == 'balance-have':
            self.currentday.addDirective(Directive().setHave(float(args[0])))
        elif instr == 'off':
            self.currentday.addOff(float(args[0]))
        elif instr == 'hours':
            self.currentday.setHours(float(args[0]), float(args[1]))
        elif instr == 'leave':
            if len(args) == 2:
                self.currentday.addLeave(float(args[0]))
                self.currentday.addComment('leave: ' + args[1])
            else:
                self.msg('Weird leave spec <' + argliststring + '>.')
        else:
            self.msg('Weird instruction <' + argliststring + '>.')

class Status:
    def __init__(self, name):
        self.name = name
        self.reset()

    def reset(self):
        self.musthours = 0
        self.havehours = 0
        self.leavebalancehours = 0
        self.leavetakenhours = 0
        self.illhours = 0
        self.workedhours = 0

    def increaseMustHours(self, dt):
        # public holidays?
        workday = not isWeekend(dt)
        if workday:
            self.musthours += 8
        return workday
    
    def processDay(self, day):
        if day.directives != None:
            for di in day.directives:
                self.processDirective(di)

        self.musthours += day.calcRequired()
        self.havehours += day.calcBalance()
        self.workedhours += day.calcWorked()
        self.illhours += day.ill
        self.leavebalancehours -= day.leave
        self.leavetakenhours += day.leave
        
    def processDirective(self, di):
        if di.reset:
            self.dump()
            self.reset()
            #print('--- reset ' + self.name + '---')
        elif di.leave != None:
            self.leavebalancehours += di.leave
        elif di.must != None:
            self.musthours = di.must
        elif di.have != None:
            self.havehours = di.have
        
    def dump(self):
        print(self.name + ': must = {0:6.2f}, worked = {1:6.2f}, ill = {2:6.2f}, leave taken= {3:6.2f}, leave left = {4:6.2f}, have = {5:6.2f}'\
              .format(self.musthours, self.workedhours, self.illhours, self.leavetakenhours, self.leavebalancehours, self.havehours))

class Statistics:
    def __init__(self, universe):
        self.days = universe.getChronoDays()
        self.globalbalance = Status('global')
        self.weeklybalance = Status('weekly')
        self.previous = None

    def processGap(self, d1, dayfilter):
        if self.previous == None:
            return

        d = self.previous.date.toordinal() + 1
        end = d1.date.toordinal()

        while d < end:
            dt = date.fromordinal(d)
            if dayfilter.passes(Day(dt)) and self.globalbalance.increaseMustHours(dt):
                print('missing weekday record for ' + str(dt))
            d = d + 1

    def checkDays(self, dayfilter):
        for d in self.days:
            if dayfilter.passes(d):
                worked = d.calcWorked()
                tasked = d.calcActivity()
                delta = tasked - worked
                if delta != 0.0:
                    print('*** {0:s} : worked = {1:5.2f}, tasked = {2:5.2f}, delta = {3:5.2f}'
                          .format(d.date.strftime('%Y-%m-%d, %a'), worked, tasked, delta))
        
    def calcBalance(self, dayfilter):
        self.previous = None
        for d in self.days:
            self.processGap(d, dayfilter)
            if dayfilter.passes(d):
                if d.date.isoweekday() == 1:
                    self.weeklybalance.dump()
                    print()
                    self.weeklybalance.reset()
                    
                self.weeklybalance.processDay(d)
                self.globalbalance.processDay(d)
                d.dump()
                self.previous = d

        self.weeklybalance.dump()
        self.globalbalance.dump()

def showUsage(cmd):
    print()
    print('  Usage: ' + cmd + ' [options] <infile> [..]')
    print('''
  TimeFlies v. {0:s} -- Copyright (C) 2012 Joerg Bullmann (jb@heilancoo.net)

  This is a simple work log and task tree processor. Projects can be
  defined in form of hierarchical task trees. Daily work progress is logged
  in form of day records with attached activities.

  This program comes with ABSOLUTELY NO WARRANTY. This is free software,
  and you are welcome to redistribute it under certain conditions. You
  should have received a copy of the GNU General Public License along
  with this program. If not, see <http://www.gnu.org/licenses/>.

  Options:

  -h, --help : show this info
  -c, --copyright : show copyright info
  -w, --work-hours <yyyy-mm> : calculate the total must/have/leave/ill
      work hour balance
  -d, --day-check <yyyy-mm> : check the daily work time vs. booked
      task time; helps to find unaccounted for time at work
  -t, --tasks <yyyy-mm> : calculate hours worked on tasks for the
      given month
  -s, --show-tasks : show the task tree
  -a, --activities : show activities in task tree output for option -t or -s
  -i, --indentation <width> : indent each level in the task hierarchy by
      <width> space characters; default: 4
'''.format(version))

def makeFilter(arg):
    if arg == 'all':
        return AllFilter()
    else:
        year, month = arg.split('-')
        return MonthFilter(int(year), int(month))

def main(argv):
    jobs = []
    opts, args = None, None
    dumpopts = {}
    dumpopts['indent'] = '    '
    
    try:
        opts, args = getopt.getopt(argv[1:], 'hcasi:w:d:t:',
                                   ['copyright', 'help', 'activities', 'show-tasks',
                                    'indentation=',
                                    'work-hours=', 'day-check=', 'tasks='])

        for opt, val in opts:
            if opt == '-h' or opt == '--help':
                showUsage(argv[0])
            elif opt == '-c' or opt == '--copyright':
                print(cpyrght.format(version))
            elif opt == '-a' or opt == '--activities':
                dumpopts['activities'] = True
            elif opt == '-i' or opt == '--indentation':
                dumpopts['indent'] = ' ' * int(val)
            elif opt == '-w' or opt == '--work-hours':
                jobs.append(('work-hours', val))
            elif opt == '-d' or opt == '--day-check':
                jobs.append(('day-check', val))
            elif opt == '-t' or opt == '--tasks':
                jobs.append(('tasks', val))
            elif opt == '-s' or opt == '--show-tasks':
                jobs.append(('show-tasks', val))

    except getopt.GetoptError as e:
        print(argv[0] + ': ' + str(e))
        print('Get help with ' + argv[0] + ' --help')
        exit()
        
    u = Universe()
    r = Reader(u)
    for f in args:
        r.read(f)
    s = Statistics(u)
    
    for j, arg in jobs:
        if j == 'day-check':
            print('Day check (' + arg + '):')
            f = makeFilter(arg)
            s.checkDays(f)
        elif j == 'tasks':
            print('Task summary (' + arg + '):')
            f = makeFilter(arg)
            act = u.taskroot.calcActivity(f)
            act.dump(dumpopts)
        elif j == 'work-hours':
            print('Work hour overview (' + arg + '):')
            f = makeFilter(arg)
            s.calcBalance(f)
        elif j == 'show-tasks':
            print('Task breakdown:')
            u.taskroot.dump(dumpopts)
            
if __name__ == '__main__':
    main(sys.argv)





