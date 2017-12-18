#!/usr/bin/env python2
"""This file handles the writing of the scoring lines Gerber file
--------------------------------------------------------------------

This program is licensed under the GNU General Public License (GPL)
Version 3.  See http://www.fsf.org for details of the license.

Rugged Circuits LLC
http://ruggedcircuits.com/gerbmerge
"""

import config
import util
import makestroke

# Add a horizontal line if its within the extents of the panel. Also, trim
# start and/or end points to the extents.
def addHorizontalLine(Lines, x1, x2, y, extents):
  assert (x1 < x2)

  # For a horizontal line, y must be above extents[1] and below extents[3].
  if extents[1] < y < extents[3]:
    # Now trim endpoints to be greater than extents[0] and below extents[2]
    line = (max(extents[0], x1), y, min(extents[2], x2), y)
    Lines.append(line)

# Add a vertical line if its within the extents of the panel. Also, trim
# start and/or end points to the extents.
def addVerticalLine(Lines, x, y1, y2, extents):
  assert (y1 < y2)

  # For a vertical line, x must be above extents[0] and below extents[2].
  if extents[0] < x < extents[2]:
    # Now trim endpoints to be greater than extents[1] and below extents[3]
    line = (x, max(extents[1], y1), x, min(extents[3], y2))
    Lines.append(line)

def isHorizontal(line):
  return line[1]==line[3]

def isVertical(line):
  return line[0]==line[2]

def clusterOrdinates(values):
  """Create a list of tuples where each tuple is a variable-length list of items
  from 'values' that are all within 2 mils of each other."""

  # First, make sure the values are sorted. Then, take the first one and go along
  # the list clustering as many as possible.
  values.sort()
  currCluster = None
  L = []
  for val in values:
    if currCluster is None:
      currCluster = (val,)
    else:
      if (val - currCluster[0]) <= 0.002:
        currCluster = currCluster + (val,)
      else:
        L.append(currCluster)
        currCluster = (val,)
    
  if currCluster is not None:
    L.append(currCluster)

  return L

def mergeHLines(Lines):
  """Lines is a list of 4-tuples (lines) that have nearly the same Y ordinate and are to be
  optimized by combining overlapping lines."""

  # First, make sure lines are sorted by starting X ordinate and that all lines
  # proceed to the right.
  Lines.sort()
  for line in Lines:
    assert line[0] < line[2]

  # Obtain the average value of the Y ordinate and use that as the Y ordinate for
  # all lines.
  yavg = 0.0
  for line in Lines:
    yavg += line[1]
  yavg /= len(Lines)

  NewLines = []

  # Now proceed to pick off one line at a time and try to merge it with
  # the next one in sequence.
  currLine = None
  for line in Lines:
    if currLine is None:
      currLine = line
    else:
      # If the line to examine starts to the left of (within 0.002") the end
      # of the current line, extend the current line.
      if line[0] <= currLine[2]+0.002:
        currLine = (currLine[0], yavg, max(line[2],currLine[2]), yavg)
      else:
        NewLines.append(currLine)
        currLine = line

  NewLines.append(currLine)

  return NewLines

def sortByY(A,B):
  "Helper function to sort two lines (4-tuples) by their starting Y ordinate"
  return cmp(A[1], B[1])

def mergeVLines(Lines):
  """Lines is a list of 4-tuples (lines) that have nearly the same X ordinate and are to be
  optimized by combining overlapping lines."""

  # First, make sure lines are sorted by starting Y ordinate and that all lines
  # proceed up.
  Lines.sort(sortByY)
  for line in Lines:
    assert line[1] < line[3]

  # Obtain the average value of the X ordinate and use that as the X ordinate for
  # all lines.
  xavg = 0.0
  for line in Lines:
    xavg += line[0]
  xavg /= len(Lines)

  NewLines = []

  # Now proceed to pick off one line at a time and try to merge it with
  # the next one in sequence.
  currLine = None
  for line in Lines:
    if currLine is None:
      currLine = line
    else:
      # If the line to examine starts below (within 0.002") the end
      # of the current line, extend the current line.
      if line[1] <= currLine[3]+0.002:
        currLine = (xavg, currLine[1], xavg, max(line[3],currLine[3]))
      else:
        NewLines.append(currLine)
        currLine = line

  NewLines.append(currLine)

  return NewLines

def mergeLines(Lines):
  # All lines extend up (vertical) and to the right (horizontal). First, do
  # simple merges. Sort all lines, which will order the lines with starting
  # points in increasing X order (i.e., to the right).
  Lines.sort()

  # Now sort the lines into horizontal lines and vertical lines. For each
  # ordinate, group all lines by that ordinate in a dictionary. Thus, all
  # horizontal lines will be grouped together by Y ordinate, and all
  # vertical lines will be grouped together by X ordinate.
  HLines = {}
  VLines = {}

  for line in Lines:
    if isHorizontal(line):
      try:
        HLines[line[1]].append(line)
      except KeyError:
        HLines[line[1]] = [line]
    else:
      try:
        VLines[line[0]].append(line)
      except KeyError:
        VLines[line[0]] = [line]

  # I don't think the next two blocks of code are necessary (merging lines
  # that are at exactly the same ordinate) since the last two blocks of
  # code do the same thing more generically by merging lines at close-enough
  # ordinates.

  # Extend horizontal lines
  NewHLines = {}
  for yval,lines in HLines.items():
    # yval is the Y ordinate of this group of lines. lines is the set of all
    # lines with this Y ordinate.
    NewHLines[yval] = []
    
    # Try to extend the first element of this list, which will be the leftmost.
    xline = lines[0]
    for line in lines[1:]:
      # If this line's left edge is within 2 mil of the right edge of the line
      # we're currently trying to grow, then grow it.
      if abs(line[0] - xline[2]) <= 0.002:    # Arbitrary 2mil?
        # Extend...
        xline = (xline[0], xline[1], line[2], xline[1])
      else:
        # ...otherwise, append the currently-extended line and make this
        # line the new one we try to extend.
        NewHLines[yval].append(xline)
        xline = line
    NewHLines[yval].append(xline)

  # Extend vertical lines
  NewVLines = {}
  for xval,lines in VLines.items():
    # xval is the X ordinate of this group of lines. lines is the set of all
    # lines with this X ordinate.
    NewVLines[xval] = []
    
    # Try to extend the first element of this list, which will be the bottom-most.
    xline = lines[0]
    for line in lines[1:]:
      # If this line's bottom edge is within 2 mil of the top edge of the line
      # we're currently trying to grow, then grow it.
      if abs(line[1] - xline[3]) <= 0.002:    # Arbitrary 2mil?
        # Extend...
        xline = (xline[0], xline[1], xline[0], line[3])
      else:
        # ...otherwise, append the currently-extended line and make this
        # line the new one we try to extend.
        NewVLines[xval].append(xline)
        xline = line
    NewVLines[xval].append(xline)

  HLines = NewHLines
  VLines = NewVLines
  NewHLines = []
  NewVLines = []

  # Now combine lines that have their endpoints either very near each other
  # or within each other. We will have to sort all horizontal lines by their
  # Y ordinates and group them according to Y ordinates that are close enough
  # to each other.
  yvals = HLines.keys()
  clusters = clusterOrdinates(yvals)  # A list of clustered tuples containing yvals

  for cluster in clusters:
    clusterLines = []
    for yval in cluster:
      clusterLines.extend(HLines[yval])

    # clusterLines is now a list of lines (4-tuples) that all have nearly the same
    # Y ordinate. Merge them together.
    NewHLines.extend(mergeHLines(clusterLines))

  xvals = VLines.keys()
  clusters = clusterOrdinates(xvals)
  for cluster in clusters:
    clusterLines = []
    for xval in cluster:
      clusterLines.extend(VLines[xval])

    # clusterLines is now a list of lines (4-tuples) that all have nearly the same
    # X ordinate. Merge them together.
    NewVLines.extend(mergeVLines(clusterLines))

  Lines = NewHLines + NewVLines

  return Lines

# Main entry point. Gerber file has already been opened, header written
# out, 1mil tool selected.
def writeScoring(fid, Place, OriginX, OriginY, MaxXExtent, MaxYExtent, AddConnectors = True):
  # For each job, write out 4 score lines, above, to the right, below, and
  # to the left. After we collect all potential scoring lines, we worry
  # about merging, etc.
  dx = config.Config['xspacing']/2.0
  dy = config.Config['yspacing']/2.0
  extents = (OriginX, OriginY, MaxXExtent, MaxYExtent)

  print "BEGIN"
  Lines = []
  for layout in Place.jobs:
    x = layout.x - dx
    y = layout.y - dy
    X = layout.x + layout.width_in() + dx
    Y = layout.y + layout.height_in() + dy

    # Just so we don't get 3.75000000004 and 3.75000000009, we round to
    # 2.5 limits.
    x,y,X,Y = [round(val,5) for val in [x,y,X,Y]]

    if config.Config['scoringstyle'] and config.Config['scoringstyle'] == 'surround' : # Scoring lines go all the way across the panel now
      addHorizontalLine(Lines, x, X, Y, extents)   # above job
      addVerticalLine(Lines, X, y, Y, extents)     # to the right of job
      addHorizontalLine(Lines, x, X, y, extents)   # below job
      addVerticalLine(Lines, x, y, Y, extents)     # to the left of job
      
      # For each job, find a suitable connector to a 
      ConnectionPoints = layout.getScoringLineConnectionPoints()
      if AddConnectors and len(ConnectionPoints):        
        Connector = None
        
        # Try the top connector
        if Connector == None and Y < extents[3]:
          print "Use Top"
          print ConnectionPoints
          Connector = [ 'V', ConnectionPoints[0], ConnectionPoints[1] ]
        
        # Try the bottom connector
        elif Connector == None and y > extents[1]:
          print "Use Bot"
          print ConnectionPoints
          Connector = [ 'V', ConnectionPoints[4], ConnectionPoints[5]-(dy*1.1) ]
        
        # Try the right connector
        elif Connector == None and X < extents[2]:
          print "Use Rgt"
          print ConnectionPoints
          Connector = [ 'H', ConnectionPoints[2], ConnectionPoints[3] ]
       
        # Try the left connector
        elif Connector == None and x > extents[0]:
          print "Use Lft"
          print ConnectionPoints
          Connector = [ 'H', ConnectionPoints[6], ConnectionPoints[7]-(dx*1.1) ]
        
        # If we found a connector, Yay, draw it
        if Connector != None:
          if Connector[0] == 'V':
            print "Add Vertical"
            print Connector
            addVerticalLine(Lines, Connector[1], Connector[2], Connector[2]+dy*1.1, extents)
          
          if Connector[0] == 'H':
            print "Add Horizontal"
            addHorizontalLine(Lines, Connector[1], Connector[1]+dx*1.1, Connector[2], extents)
            
    else:
      addHorizontalLine(Lines, OriginX, MaxXExtent, Y, extents)   # above job
      addVerticalLine(Lines, X, OriginY, MaxYExtent, extents)     # to the right of job
      addHorizontalLine(Lines, OriginX, MaxXExtent, y, extents)   # below job
      addVerticalLine(Lines, x, OriginY, MaxYExtent, extents)     # to the left of job

  print "END"
      

  # Combine disparate lines into single lines
  Lines = mergeLines(Lines)

  #for line in Lines:
  #  print [round(x,3) for x in line]

  # Write 'em out  
  if config.Config['fiducialpoints'] and config.Config['fiducialpoints'] == 'scoring':
    # If fiducialpoints == 'scoring' rewrite it now to mark out the scoring lines
    newFiducuals = [ ]    
    
    for line in Lines:
      # Fiducials at 10% in from each end of the line
      if isHorizontal(line):
        offset = (line[2]-line[0])*0.1
        newFiducuals.append(line[0]+offset)
        newFiducuals.append(line[1])
        newFiducuals.append(line[2]-offset)
        newFiducuals.append(line[3])
      else:
        offset = (line[3]-line[1])*0.1
        newFiducuals.append(line[0])
        newFiducuals.append(line[1]+offset)
        newFiducuals.append(line[2])
        newFiducuals.append(line[3]-offset)
      
      # Fiducials at the end of each line, unless it's a board edge
      #  (in other words, line intersections)
      # I think this makes it a bit cluttered
      if 0:
        if not( line[0] == OriginX or line[1] == OriginY or line[0] == MaxXExtent or line[1] == MaxYExtent):
          newFiducuals.append(line[0])
          newFiducuals.append(line[1])
          
        if not( line[2] == OriginX or line[3] == OriginY or line[2] == MaxXExtent or line[3] == MaxYExtent):
          newFiducuals.append(line[2])
          newFiducuals.append(line[3])
      
      # Fiducials at 50% of each line  
      if isHorizontal(line):
        offset = (line[2]-line[0])*0.5
        newFiducuals.append(line[0]+offset)
        newFiducuals.append(line[1])
      else:
        offset = (line[3]-line[1])*0.5
        newFiducuals.append(line[0])
        newFiducuals.append(line[1]+offset)
      
    config.Config['fiducialpoints'] = ','.join(map(str, newFiducuals))
  
  if fid != None:
    for line in Lines:
      makestroke.drawPolyline(fid, [(util.in2gerb(line[0]),util.in2gerb(line[1])), \
                                    (util.in2gerb(line[2]),util.in2gerb(line[3]))], 0, 0)

# vim: expandtab ts=2 sw=2 ai syntax=python
