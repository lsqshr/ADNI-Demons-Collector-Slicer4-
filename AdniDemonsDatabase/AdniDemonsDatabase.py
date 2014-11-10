import os
from os.path import join
from sets import Set
import re
import csv
import time
import numpy as np
from collections import Counter
from threading import BoundedSemaphore
import unittest
import subprocess
import multiprocessing
import threading
import Queue
from itertools import tee, izip
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer import mrmlScene as scene
from exceptions import NotImplementedError

class AdniDemonsDatabase:
  def __init__(self, parent):
    parent.title        = "ADNI Demons Database"
    parent.categories   = ["Content Based Retrieval"]
    parent.dependencies = []
    parent.contributors = ["Siqi Liu (USYD), Sidong Liu (USYD, BWH)"]
    parent.helpText     = ""
    parent.acknowledgementText = ""
    self.parent = parent


    # Add this test to the SelfTest module's list for discovery when the module
    # is created. Since this module may be discovered before SelfTests itself,
    # create the list if it doesn't already exist.
    try:
      slicer.selfTests
    except AttributeError:
      slicer.selfTests = {}
      slicer.selfTests['AdniDemonsDatabase'] = self.runTest

  def runTest(self):
      tester = AdniDemonsDatabaseTest()
      tester.runTest()

#
# qAdniDemonsDatabaseWidget
#

class AdniDemonsDatabaseWidget(ScriptedLoadableModuleWidget):

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    self.dbpath = None
    self.dbcsvpath = None
    self.flirttemplate = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain.nii.gz' 

    #
    # Reload and Test area
    #
    reloadCollapsibleButton       = ctk.ctkCollapsibleButton()
    reloadCollapsibleButton.text  = "Reload && Test"
    self.layout.addWidget(reloadCollapsibleButton)
    reloadFormLayout              = qt.QFormLayout(reloadCollapsibleButton) 

    self.clearButton              = qt.QPushButton("Clear Scene")
    self.clearButton.toolTip      = "Clear all the volumes and models in 3D views"
    self.clearButton.name         = "AdniDemonsDatabase Clear"
    reloadFormLayout.addWidget(self.clearButton)
    self.clearButton.connect('clicked()', self.onClear)

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadButton             = qt.QPushButton("Reload")
    self.reloadButton.toolTip     = "Reload AdniDemonsDatabase"
    self.reloadButton.name        = "AdniDemonsDatabase Reload"
    reloadFormLayout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked()', self.onReload)

    # Get the test methods create a button for each of them
    testklsdir = dir(AdniDemonsDatabaseTest)
    # reload and test button
    # (use this during development, but remove it when delivering your module to users)
    # reload and run specific tests
    # scenarios                     = ('All', 'Model', 'Volume', 'SceneView_Simple', 'SceneView_Complex')
    scenarios = [n for n in testklsdir if n.startswith('test_')]

    for scenario in scenarios:
        button                      = qt.QPushButton("Reload and Test %s" % scenario)
        button.toolTip              = "Reload this module and then run the self test on %s." % scenario
        reloadFormLayout.addWidget(button)
        button.connect('clicked()', lambda s = scenario: self.onReloadAndTest(scenario = s))

    #
    # Test All Button
    #
    self.testallButton             = qt.QPushButton("Test All")
    self.testallButton.toolTip     = "Run all the logic tests"
    self.testallButton.name        = "Reload & Test All"
    reloadFormLayout.addWidget(self.testallButton)
    self.testallButton.connect('clicked()', self.onTestAll)

    #
    # Settings Area
    #
    settingCollapsibleButton      = ctk.ctkCollapsibleButton()
    settingCollapsibleButton.text = "ADNI Demons Database Generation"
    self.layout.addWidget(settingCollapsibleButton)
    settingFormLayout             = qt.QGridLayout(settingCollapsibleButton) 

    #
    # DB Directory Selection Button
    #
    self.dbButton                 = qt.QPushButton("Set ADNI Database Directory")
    self.dbButton.toolTip         = "Set ANDI Database Directory"
    self.dbButton.enabled         = True 
    settingFormLayout.addWidget(self.dbButton, 0, 0)
    self.dblabel = qt.QLabel(self.dbpath if self.dbpath != None else 'Empty')
    settingFormLayout.addWidget(self.dblabel, 0, 1)

    #
    # DB csv file Selection Button
    #
    csvbtntxt = "Set *.csv File For DB Record"
    self.dbcsvpath = '' if self.dbButton.text.find(':') == -1 else join(self.dbpath, 'db.csv')
    self.csvButton                 = qt.QPushButton(csvbtntxt if len(self.dbcsvpath) == 0 else csvbtntxt + ' : ' + self.dbcsvpath)
    self.csvButton.toolTip         = "Set ANDI Database csv file path, which can be downloaded in the data collection"
    self.csvButton.enabled         = True 
    settingFormLayout.addWidget(self.csvButton, 1, 0)
    self.csvlabel = qt.QLabel(self.dbcsvpath if self.dbcsvpath != None and self.dbpath != None else 'Empty')
    settingFormLayout.addWidget(self.csvlabel, 1, 1)

    #
    # Flirt Template Selection Button
    #
    self.betflirt_templatebutton                 = qt.QPushButton("Select Flirt Template")
    self.betflirt_templatebutton.toolTip         = "Select Flirt Template"
    self.betflirt_templatebutton.enabled         = True 
    settingFormLayout.addWidget(self.betflirt_templatebutton, 2, 0)
    self.flirtlabel = qt.QLabel(self.flirttemplate if self.flirttemplate != None else 'Empty')
    settingFormLayout.addWidget(self.flirtlabel, 2, 1)

    # They should be connected afterwards their initiation
    self.dbButton.connect('clicked(bool)', lambda: self.onFileButton('db'))
    self.csvButton.connect('clicked(bool)', lambda: self.onFileButton('csv'))
    self.betflirt_templatebutton.connect('clicked(bool)', lambda: self.onFileButton('flirt'))

    #
    # Bet & Flirt Threshold
    #
    self.betflirtspin = qt.QDoubleSpinBox()
    self.betflirtspin.setRange(0.0, 1.0)
    self.betflirtspin.setSingleStep(0.05)
    self.betflirtspin.setValue(0.2)
    settingFormLayout.addWidget(qt.QLabel("Bet Threashold"), 3 ,0)
    settingFormLayout.addWidget(self.betflirtspin, 3, 1)

    #
    # Checkbox for Bet & Flirt
    #
    self.betflirtcheck = qt.QCheckBox("Run Bet + Flirt")
    self.betflirtcheck.setToolTip("Only the image IDs listed in the csv file will be processed. flirted images will be saved in path/to/db/flirted")
    self.betflirtcheck.checked = 0
    settingFormLayout.addWidget(self.betflirtcheck, 4, 0)

    #
    # Checkbox for Running Demons Registration 
    #
    self.demonscheck = qt.QCheckBox("Run Demons")
    self.demonscheck.setToolTip("Only the image IDs listed in the csv file will be processed. Image sources will only be retrieved from path/to/db/flirted")
    self.demonscheck.checked = 0
    self.demonscheck.enabled = True 
    settingFormLayout.addWidget(self.demonscheck, 4, 1)

    #
    # Interval Selection : 6m | 12m
    #
    self.intervalCombo = qt.QComboBox()
    self.intervalCombo.addItem("6 Month")
    self.intervalCombo.addItem("12 Month")
    settingFormLayout.addWidget(qt.QLabel("Extract Interval"), 5 ,0)
    settingFormLayout.addWidget(self.intervalCombo, 5, 1)

    #
    # Sequence Label Selection: All, Stable: NL, Stable: MCI, Stable: AD, NL2MCI, MCI2AD 
    #
    self.seqCombo = qt.QComboBox()
    self.seqCombo.enabled = False 
    self.seqCombo.addItems(["All", "Stable: NL", "Stable: MCI", "Stable: AD", "NL2MCI", "MCI2AD"])
    settingFormLayout.addWidget(qt.QLabel("Sequence Type"), 6 ,0)
    settingFormLayout.addWidget(self.seqCombo, 6, 1)

    actionCollapsibleButton       = ctk.ctkCollapsibleButton()
    actionCollapsibleButton.text  = "Database Generation Actions"
    self.layout.addWidget(actionCollapsibleButton)
    actionFormLayout              = qt.QFormLayout(actionCollapsibleButton) 

    #
    # Generate Database csv
    #
    self.dbgenButton = qt.QPushButton("Generate Database Sequence csv")
    self.dbgenButton.toolTip = "Generate A csv with required fields by merging the image collection csv and the dxsum. To make this button functional, pls make sure R language is installed in your system and \'RScript\' is in the $PATH. \'dbgen.csv\' will be generated in the database directory"
    self.dbgenButton.enabled = False 
    actionFormLayout.addRow(self.dbgenButton)
    self.dbgenButton.connect('clicked(bool)', self.onDbgenButton)

    #
    # Validate Database see if all the images exist 
    #
    self.validateDbButton = qt.QPushButton("Validate Database")
    self.validateDbButton.toolTip = "Check if all the image ids in the dbgen.csv exist in the data folder"
    self.validateDbButton.enabled = False 
    actionFormLayout.addRow(self.validateDbButton)
    self.validateDbButton.connect('clicked(bool)', self.onValidateDbButton)

    #
    # Validate Bet and Flirt see if all the images were flirted and betted successfully 
    #
    self.validateBetAndFlirtButton = qt.QPushButton("Validate Bet&Flirt")
    self.validateBetAndFlirtButton.toolTip = "Check if all the image were successfully betted and flirted"
    self.validateBetAndFlirtButton.enabled = True 
    actionFormLayout.addRow(self.validateBetAndFlirtButton)
    self.validateBetAndFlirtButton.connect('clicked(bool)', self.onValidateBetAndFlirtButton)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = True 
    actionFormLayout.addRow(self.applyButton)
    self.applyButton.connect('clicked(bool)', self.onApplyButton)

    #
    # Flirt Clear Button
    #
    self.clearFlirtButton = qt.QPushButton("Clear Flirt")
    self.clearFlirtButton.toolTip = "Clear the files created by flirt."
    self.clearFlirtButton.enabled = False
    actionFormLayout.addRow(self.clearFlirtButton)
    self.clearFlirtButton.connect('clicked(bool)', self.onFlirtClear)

    #
    # Evaluate DB Area
    #
    evaluateCollapsibleButton      = ctk.ctkCollapsibleButton()
    evaluateCollapsibleButton.text = "Evaluate DB"
    self.layout.addWidget(evaluateCollapsibleButton)
    evaluateFormLayout             = qt.QGridLayout(evaluateCollapsibleButton) 

    #
    # MAP setting
    #
    self.kmapspin = qt.QDoubleSpinBox()
    self.kmapspin.setRange(0.0, 10.0)
    self.kmapspin.setSingleStep(1.0)
    self.kmapspin.setValue(5)
    evaluateFormLayout.addWidget(qt.QLabel("K value for MAP"), 1 ,0)
    evaluateFormLayout.addWidget(self.kmapspin, 1, 1)

    #
    # DB Evaluate Button
    #
    self.evaluateDbButton = qt.QPushButton('Evaluate DB')
    self.evaluateDbButton.toolTip = "Set ANDI Database Directory. Assume in this folder, you have already generated a database with ADNI Demons DB Creator"
    self.evaluateDbButton.enabled = True 
    evaluateFormLayout.addWidget(self.evaluateDbButton, 2, 0)
    self.evaluateDbButton.connect('clicked(bool)', self.onEvaluateDbButton)

    #
    # Regenerate DB matrix check
    #
    self.regenMatCheck = qt.QCheckBox('Regenerate Dissimilarity Matrix')
    self.regenMatCheck.checked = False
    self.regenMatCheck.enabled = True
    evaluateFormLayout.addWidget(self.regenMatCheck, 2, 1)

    #
    # Testing Ariea
    #
    statusCollapsibleButton = ctk.ctkCollapsibleButton()
    statusCollapsibleButton.text  = "Console"
    self.layout.addWidget(statusCollapsibleButton)
    self.statusLayout              = qt.QFormLayout(statusCollapsibleButton) 

    #
    # Show a Return Message
    #
    self.returnMsg = qt.QLabel("Ready") 
    self.statusLayout.addRow(self.returnMsg)

    # Add vertical spacer
    self.layout.addStretch(1)

  # -------------------------------------
  def onClear(self):
    slicer.mrmlScene.Clear(0)

  # ---------------------------------------------
  def onReloadAndTest(self, moduleName = "AdniDemonsDatabase", scenario = None):
    try:
      self.onReload(moduleName)
      evalString = 'globals()["%s"].%sTest()' % (moduleName, moduleName)
      tester = eval(evalString)
      tester.runTest(scenario = scenario)
    except Exception, e:
      import traceback
      traceback.print_exc()
      qt.QMessageBox.warning(slicer.util.mainWindow(),
          "Reload and Test", 'Exception!\n\n' + str(e) + "\n\nSee Python Console for Stack Trace")

  # ----------------------------------------------
  def onReload(self, moduleName = "AdniDemonsDatabase"): 
    """
    Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    import imp, sys, os, slicer

    widGetName = moduleName + "Widget"

    # reload the source code
    # - set source f path
    # - load the module to the global space
    fPath = eval('slicer.modules.%s.path' % moduleName.lower())
    p = os.path.dirname(fPath)
    if not sys.path.__contains__(p):
      sys.path.insert(0,p)
    fp = open(fPath, "r")
    globals()[moduleName] = imp.load_module(
        moduleName, fp, fPath, ('.py', 'r', imp.PY_SOURCE))
    fp.close()

    # rebuild the widget
    # - find and hide the existing widget
    # - create a new widget in the existing parent
    parent = slicer.util.findChildren(name = '%s Reload' % moduleName)[0].parent().parent()
    for child in parent.children():
      try:
        child.hide()
      except AttributeError:
        pass
    # Remove spacer items
    item = parent.layout().itemAt(0)
    while item:
      parent.layout().removeItem(item)
      item = parent.layout().itemAt(0)
    # create new widget inside existing parent
    globals()[widGetName.lower()] = eval('globals()["%s"].%s(parent)' % (moduleName, widGetName))
    globals()[widGetName.lower()].setup()

  def onTestAll(self):
    self.onReload()
    test = AdniDemonsDatabaseTest()
    test.runTest()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector.currentNode() and self.outputSelector.currentNode()

  ###
  # Callbacks of Generator Buttons
  ###
  def onValidateDbButton(self):
    logic = AdniDemonsDatabaseLogic(self.dbpath)
    logic.validatedb()

  def onValidateBetAndFlirtButton(self):
    logic = AdniDemonsDatabaseLogic(self.dbpath)
    logic.validatebetflirt()

  def onApplyButton(self):
    logic = AdniDemonsDatabaseLogic(self.dbpath)
    if not os.path.exists(join(self.dbpath, 'dbgen.csv')):
      self.onDbgenButton()

    if self.betflirtcheck.checked == 1:
      self.returnMsg.text = 'bet & flirting...'
      logic.betandflirtall(self.flirttemplate, self.betflirtspin.text)
      self.demonscheck.enabled = True

    if self.demonscheck.checked == 1:
      self.returnMsg.text = 'Collecting demons...'
      intervaltxt = self.intervalCombo.currentText
      num, month = intervaltxt.split(' ')
      logic.demonsall(int(num))

  # Add/Replace the path after the button text
  def _updateBtnTxt(self, btn, newpath):
    btntxt = btn.text
    splt = btntxt.find(':')
    btn.text = btntxt + " : " + "\"%s\"" % newpath if splt == -1 else btntxt[:splt + 2]  + "\"%s\"" % newpath 

  def onFileButton(self, target): # 'db'/'csv'/'flirt'
    dbDialog = qt.QFileDialog()
    dbDialog.setFileMode(2 if 'db' else 1)
    if target == 'db':
      self.dbpath = dbDialog.getExistingDirectory()
      #self._updateBtnTxt(self.dbButton, self.dbpath)
      self.dblabel.text = self.dbpath
      self.dbcsvpath = join(self.dbpath, 'db.csv')
      #self._updateBtnTxt(self.csvButton, self.dbcsvpath)
      self.csvlabel.text = self.dbcsvpath

      # If ./betted or ./flirted exist in the dbpath, enable clear flirt button
      if os.path.exists(join(self.dbpath, 'betted')) or \
              os.path.exists(join(self.dbpath, 'betted')) :
          self.clearFlirtButton.enabled = True                

      # If db.csv exists, enable dbgen button
      if os.path.exists(join(self.dbpath, 'db.csv')):
          self.dbgenButton.enabled = True

      # If dbgen.csv exists, enable validatedb button
      if os.path.exists(join(self.dbpath, 'dbgen.csv')):
          self.validateDbButton.enabled = True

    elif target == 'csv':
      self.dbcsvpath = dbDialog.getOpenFileName()
      #self._updateBtnTxt(self.csvButton, self.dbcsvpath)
      self.csvlabel.text = self.dbcsvpath
    elif target == 'flirt':
      self.flirttemplate = dbDialog.getOpenFileName()
      #self._updateBtnTxt(self.betflirt_templatebutton, self.flirttemplate)
      self.flirtlabel.text = self.flirttemplate

  def onDbgenButton(self):
    if self.dbpath is None or self.dbcsvpath is None:
      '''
      msgb = qt.QMessageBox();
      msgb.setText('Unknown DB path')
      msgb.setStandardButtons(qt.QMessageBox.Cancel)
      msgb.show() # .show() does not work. should make it .exec()
      '''
      self.returnMsg.text = 'Unknown DB Path'
    else:
      logic = AdniDemonsDatabaseLogic(self.dbpath)
      logic.dbgen(self.dbcsvpath)

      # If dbgen.csv exists, enable validatedb button
      if os.path.exists(join(self.dbpath, 'dbgen.csv')):
          self.validateDbButton.enabled = True
      self.returnMsg.text = 'dbgen.csv Generated in %s' % self.dbpath

  def onFlirtClear(self):
    logic = AdniDemonsDatabaseLogic(self.dbpath)
    logic.clean()

  ###
  # Callbacks of Retriver buttons
  ###
  def onEvaluateDbButton(self):
    logic = AdniDemonsDatabaseLogic(self.dbpath)
    result = logic.evaluateDb(int(float(self.kmapspin.text)), self.regenMatCheck.checked)
    self.returnMsg = "MAP: %f" % result 
      

#
# AdniDemonsDatabaseLogic
#
class AdniDemonsDatabaseLogic(ScriptedLoadableModuleLogic):
  def __init__(self, dbpath):
    maxthread = 1
    self.pool_sema = BoundedSemaphore(maxthread)
    self.resample_sema = BoundedSemaphore(1)
    self.dbpath = dbpath

    # Status
    self.StatusModifiedEvent = slicer.vtkMRMLCommandLineModuleNode().StatusModifiedEvent
    self.CLINode = slicer.vtkMRMLCommandLineModuleNode()
    self.CLINode.SetStatus(self.CLINode.Idle)
    # VTK Signals variables
    self.Observations = []

  def _readcolumn(self, colname):
    col = []

    with open(join(self.dbpath, 'dbgen.csv')) as f:
      r = csv.reader(f)
      header = r.next()
      mididx = header.index(colname)

      for row in r:
          col.append(row[mididx])
         
    return col

  def _findimgid(self, fname): # Find the image id like IXXXXXXXX from the filename string
    lmatch = re.findall('_I\d+', fname)
    assert len(lmatch) <= 1, 'More than one matches were found: '
    cleanmatch = [] 

    for m in lmatch: 
      cleanmatch.append(m[1:]) # Remove the '_' before image id 

    return cleanmatch

  def dbgen(self, dbcsvpath):
    safedbpath = self.dbpath.replace(' ', '\ ')
    safecsvpath = dbcsvpath.replace(' ', '\ ')
    if os.path.exists(dbcsvpath): # os.path.exists can recognise spaces in paths
      os.system("Rscript %s %s %s" % (join(os.path.dirname(os.path.realpath(__file__)),\
                   'dbgen.r'), safedbpath, safecsvpath))
    else:
      print "db.csv not found in %s" % (dbcsvpath)

  def _traverseForImage(self, func, parallel = False):
    limg = [];
    # Traverse the dbpath: if the image id is wanted, bet and flirt this image
    # Only the flirted image will be saved in self.dbpath/flirted/IMAGEID.nii
    for root, dirs, files in os.walk(self.dbpath):
      for file in files:
          imgid = self._findimgid(file)
          if len(imgid) > 0:
            limg.append((root, file, imgid[0]))

    if parallel:
      nthread = multiprocessing.cpu_count()
      #lidx = [ range(len(limg))[i::nthread] for i in xrange(nthread) ] # chunk the image list into #nthread parts without order
      exitFlag = 0;

      queuelock = threading.Lock()
      workqueue = Queue.Queue(len(limg))
      threads = []
      # Define a private thread class
      class traverseworker (threading.Thread):

        def __init__(self, threadid, q, lock, func):
          threading.Thread.__init__(self)
          self.threadid = threadid
          self.q = q
          self.qlock = lock
          self.func = func

        def run(self):
          print 'Work %d started and waiting' % self.threadid
          waitting = True
          while not exitFlag:
            with self.qlock:
              if not self.q.empty():
                root, file, imgid = self.q.get()
                print 'thread %d is processing %s' % (self.threadid, imgid)
                waitting = False
            if not waitting:
              self.func(root, file, imgid)
              waitting = True

      # Start the workers
      for i in range(nthread):
        worker = traverseworker(i, workqueue, queuelock, func)
        worker.start()
        threads.append(worker)

      # Fill the queue with image meta
      queuelock.acquire()
      print 'number of images: %d' % len(limg)
      for img in limg:
        workqueue.put(img)
      queuelock.release()

      # Wait for all images to be processed
      while not workqueue.empty():
        pass

      exitFlag = 1 # Notify all threads to exit
      
      for t in threads:
        t.join()
      print 'All workers have returned'
    else:
      for img in limg:
        func(img[0], img[1], img[2])

  def validatebetflirt(self): # see if all the image ids have been generated
    # Validate Database First
    self.validatedb()
    # read in the csv and extract the image ids to be done
    limgid = self._readcolumn('Image.Data.ID')
    bettedpath = join(self.dbpath, 'betted')
    flirtedpath = join(self.dbpath, 'flirted')

    lbetid = []
    lflirtid = []

    # Validate Bet
    for f in os.listdir(bettedpath):
      limgid = self._findimgid(f)[1:]
      if len(limgid) > 0:
        lbetid.append(limgid[0][1:]) # Remove 'I'
    missingbet = Set(limgid) - Set(lbetid)

    # Validate Flirt
    for f in os.listdir(flirtedpath):
      limgid = self._findimgid(f)[1:]
      if len(limgid) > 0:
        lflirtid.append(limgid[0][1:]) # Remove 'I'
    missingflirt = Set(limgid) - Set(lbetid)

    if len(missingflirt) is not 0:
      print 'Missing Bet:\t', list(missingbet)
      print 'Missing Flirt:\t', list(missingflirt)
    else:
      print 'All images were betted and flirted'

  def betandflirtall(self, flirttemplate, betthreshold):
    # Validate Database First
    self.validatedb()

    start = time.time()
    imgctr = Counter(hit=0)
    # read in the csv and extract the image ids to be done
    limgid = self._readcolumn('Image.Data.ID')

    #safedbpath = self.dbpath.replace(' ', '\ ')
    bettedpath = join(self.dbpath, 'betted')
    flirtedpath = join(self.dbpath, 'flirted')

    if not os.path.exists(bettedpath):
      os.makedirs(bettedpath)

    if not os.path.exists(flirtedpath):
      os.makedirs(flirtedpath)

    # Traverse the dbpath: if the image id is wanted, bet and flirt this image
    # Only the flirted image will be saved in self.dbpath/flirted/IMAGEID.nii
    def betandflirt(root, file, imgid, limage):
      f, ext = os.path.splitext(file)
      if ext == '.nii' and imgid.replace('I','') in limage:
        imgctr['hit'] += 1
        print 'flirting %s' % file
        imgpath = join(root, file)
        roiimgpath = join(bettedpath, f)
        subprocess.call(['standard_space_roi', imgpath, roiimgpath, '-b'], shell=False)
        bettedimgpath = join(bettedpath, f+'.betted.nii')
        subprocess.call(['bet', join(bettedpath, f), bettedimgpath, '-f', str(betthreshold)], shell=False)
        subprocess.call(['rm', roiimgpath+'.nii.gz'])
        print 'flirtedpath:' , flirtedpath
        flirtimgpath = join(flirtedpath, f + '.flirted.nii')   
        print 'flirtimgpath: ', flirtimgpath
        subprocess.call(['flirt', '-ref', flirttemplate, '-in', bettedimgpath, '-out', flirtimgpath])
    self._traverseForImage(lambda root, file, imgid: betandflirt(root, file, imgid, limgid), parallel=True)
    end = time.time()
    print "*** finished betandflirt ***\nTotal Elapsed Time: %f.2\tAverage Time For Each Image: %f.2" % (end-start, (end-start)/imgctr['hit'])
    self.validatebetflirt()

  # Delete the generated processing results 
  def clean(self):
    subprocess.call(['rm', '-rf', join(self.dbpath, 'betted'), join(self.dbpath, 'flirted')])

  def run(self):
    fixedfile = 'flirted/ADNI_116_S_4092_MR_MPRAGE_GRAPPA2_br_raw_20120118092234173_73_S137148_I278831.flirted.nii.gz'
    movingfile = 'flirted/ADNI_116_S_4092_MR_MPRAGE_GRAPPA2_br_raw_20110624151135946_18_S112543_I241691.flirted.nii.gz'
        
    start = time.time()
    for i in range(1):
      #self.pool_sema.acquire()
      print 'running %d' % i
      self.demonregister(fixedfile, movingfile)
    avgtime = (time.time() - start) / 5
    print "Averge Running Time: %f.2" % avgtime

  def _pairwise(self, iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return izip(a, b)

  def find_file_with_imgid(self, imgid, path):
    foundfile = [ f for f in os.listdir(path) if os.path.isfile(join(path,f)) and f.endswith('.nii.gz') and '_I'+imgid in f]
    if len(foundfile) == 0:
      raise Exception('No flirt image associated with %s ' % imgid)
    elif len(foundfile) > 1:
      raise Exception('%d Duplicated image ID found for %s ' % (len(foundfile), imgid))
    return join(path, foundfile[0])

  def validatedb(self,):
    print "Validating Database"
    limgid = Set([])

    with open(join(self.dbpath, 'dbgen.csv')) as f:
      r = csv.reader(f)
      header = r.next()
      imgididx = header.index('Image.Data.ID')

      for row in r:
        imgid = row[imgididx]
        limgid.add(imgid) 

    foundimgid = Set([])
    self._traverseForImage(lambda root,file,id: foundimgid.add(id.replace('I', '')))
    dimgid = limgid - foundimgid # Difference between the csv and the imgids in the data folder
    assert len(dimgid) == 0, str(dimgid) + ' not found'
    print ("All images have been found")

  def demonsall(self, interval):
    registered = {} #<(RID, VISCODE1, VISCODE2): True/False>
    patient = {}

    # Read dbgen.csv into dict<RID, [(VISCODE, IMAGEID)]>
    with open(join(self.dbpath, 'dbgen.csv')) as f:
      r = csv.reader(f)
      header = r.next()
      rididx = header.index('RID')
      visidx = header.index('VISCODE')
      imgididx = header.index('Image.Data.ID')
      dxidx = header.index('DXCHANGE')

      for row in r:
        if row[rididx] in patient:
          patient[row[rididx]].append((row[visidx], row[imgididx], row[dxidx]))
        else:
          patient[row[rididx]] = [(row[visidx], row[imgididx], row[dxidx])]

    # For each RID, demons for the required intervals
    for i, rid in enumerate(patient):
      for v, w in self._pairwise(patient[rid]):
        vmonth = v[0].replace('m', '')
        wmonth = w[0].replace('m', '')
        if (v[1] is not w[1]) and (int(wmonth) - int(vmonth) == interval):
          try:
            fixedpath = self.find_file_with_imgid(w[1], join(self.dbpath, 'flirted'))
            movingpath = self.find_file_with_imgid(v[1], join(self.dbpath, 'flirted'))
            if not os.path.exists(fixedpath):
              raise Exception('%s does not exist' % fixedpath)
            if not os.path.exists(movingpath):
              raise Exception('%s does not exist' % movingpath)
            self.demonregister(fixedpath, movingpath)
          except Exception:
            print (rid, v[1], w[1]), ' failed'
            registered[(rid, v[1], w[1], v[2], w[2])] = False
          else:
            registered[(rid, v[1], w[1], v[2], w[2])] = True

    if len(registered) > 0:
      # Rewrite csv ./trans/demonlog.csv
      with open(join(self.dbpath, 'trans', 'demonlog.csv'), 'wb') as f:
        writer = csv.writer(f, delimiter = ',', )
        writer.writerow(['RID', 'IMAGEID-A', 'IMAGEID-B', 'DX-A', 'DX-B', 'Status'])
        for trans in registered:
          row = list(trans)
          row.append('Success' if registered[trans] else 'Fail')
          writer.writerow(row)

  def demonregister(self, fixedfile, movingfile):
    print 'Loading fixed from %s' % fixedfile
    print 'Loading moving from %s' % movingfile
    slicer.util.loadVolume(fixedfile) # Load fixed volume
    slicer.util.loadVolume(movingfile) # Load moving Volume
    fixedimgid = self._findimgid(fixedfile)[0]
    print 'Found Fixed Image ID: %s' % fixedimgid
    movingimgid = self._findimgid(movingfile)[0]
    print 'Found Moving Image ID: %s' % movingimgid
    fixedvol = slicer.util.getNode(pattern="*%s*" % fixedimgid)
    movingvol = slicer.util.getNode(pattern="*%s*" % movingimgid)
    print 'Found Nodes', fixedvol.GetID(), movingvol.GetID()

    # Create Output Volume if it does not exist
    outputvol = slicer.util.getNode('outputvol') 
    if outputvol is None:
      outputvol = slicer.vtkMRMLScalarVolumeNode()
      outputvol.SetName('outputvol')
      slicer.mrmlScene.AddNode(outputvol)
      assert slicer.util.getNode('outputvol') is not None 

    gridtransnode = slicer.vtkMRMLGridTransformNode()
    self.transname = '%s-%s' % (movingimgid[1:], fixedimgid[1:]) # Avoid from being taken as a volume
    gridtransnode.SetName(self.transname)
    slicer.mrmlScene.AddNode(gridtransnode)
    assert slicer.util.getNode(self.transname) is not None 

    # Set parameters    
    parameters = {}
    parameters['fixedVolume'] = fixedvol.GetID()
    parameters['movingVolume'] = movingvol.GetID()
    parameters['outputVolume'] = outputvol.GetID()
    parameters['outputDisplacementFieldVolume'] = gridtransnode.GetID()
    parameters['inputPixelType'] = 'float'
    parameters['outputPixelType'] = 'float'
    parameters['interpolationMode'] = 'WindowedSinc'
    parameters['registrationFilterType'] = 'Diffeomorphic'
    parameters['smoothDisplacementFieldSigma'] = '1'
    parameters['numberOfPyramidLevels'] = '5'
    parameters['numberOfPyramidLevels'] = '5'
    parameters['minimumFixedPyramid']   = '16,16,16'
    parameters['minimumMovingPyramid']  = '16,16,16'
    parameters['arrayOfPyramidLevelIterations'] = '300,50,30,20,15'
    parameters['numberOfHistogramBins'] = '256'
    parameters['numberOfMatchPoints'] = '10'
    parameters['medianFilterSize'] = '0,0,0'
    parameters['maskProcessingMode'] = 'NOMASK'
    parameters['lowerThresholdForBOBF'] = '0'
    parameters['upperThresholdForBOBF'] = '70'
    parameters['backgroundFillValue'] = '0'
    parameters['seedForBOBF'] = '0,0,0'
    parameters['neighborhoodForBOBF'] = '1,1,1'
    parameters['outputDisplacementFieldPrefix'] = 'none'
    parameters['checkerboardPatternSubdivisions'] = '4,4,4'
    parameters['gradient_type'] = '0'
    parameters['upFieldSmoothing'] = '0' 
    parameters['max_step_length'] = '2'
    parameters['numberOfBCHApproximationTerms'] = '2' 
    parameters['numberOfThreads'] = str(multiprocessing.cpu_count())
    parameters['histogramMatch'] = True

    # Run Demons Registration CLI
    demonscli = self.getCLINode(slicer.modules.brainsdemonwarp)
    self.addObserver(demonscli, self.StatusModifiedEvent, self.onFinishDemon)
    demonnode = slicer.cli.run(slicer.modules.brainsdemonwarp, demonscli, parameters, wait_for_completion=True)

    return True

  def onFinishDemon(self, cliNode, event):
    if not cliNode.IsBusy():
      self.removeObservers(self.onFinishDemon)

    print("Got a %s from a %s" % (event, cliNode.GetClassName()))
    if cliNode.IsA('vtkMRMLCommandLineModuleNode'):
      print("Status is %s" % cliNode.GetStatusString())
      if cliNode.GetStatusString() == 'Completed':
        # Save the grid trans as ./trans/MOVINGIMAGEID-FIXEDIMAGEID.h5
        gridtransnode = slicer.util.getNode(self.transname)
        assert gridtransnode is not None, 'Transform cannot be found'
        transpath = join(self.dbpath, 'trans')
        if not os.path.exists(transpath):
          print "Creating Folder: %s" % transpath
          subprocess.call(['mkdir', transpath])
        transpath = join(transpath, '%s.h5' % self.transname) # .h5 is the extention for transform in Slicer
        assert slicer.util.saveNode(gridtransnode, transpath) == True, 'Transform Node %s fail to be saved in %s' % ( gridtransnode.GetID(), transpath)

        # Clean up the volumes used in this transformation
        '''
        fixedvol = slicer.util.getNode('fixedvol')
        scene.RemoveNode(fixedvol)
        movingvol = slicer.util.getNode('movingvol')
        scene.RemoveNode(movingvol)
        outputvol = slicer.util.getNode('outputvol')
        scene.RemoveNode(outputvol)
        '''
        self.CLINode.SetStatus(self.CLINode.Completed)
        slicer.mrmlScene.Clear(0)
      else:
        self.CLINode.SetStatus(cliNode.GetStatus())

  def getCLINode(self, cliModule):
    """ Return the cli node to use for a given CLI module. Create the node in
    scene if needed.
    """
    cliNode = slicer.mrmlScene.GetFirstNodeByName(cliModule.title)

    if cliNode == None:
      cliNode = slicer.cli.createNode(cliModule)
      cliNode.SetName(cliModule.title)
    return cliNode

  def removeObservers(self, method):
    for o, e, m, g, t in self.Observations:
      if method == m:
        o.RemoveObserver(t)
        self.Observations.remove([o, e, m, g, t])

  def addObserver(self, object, event, method, group = 'none'):
    if self.hasObserver(object, event, method):
      print 'already has observer'
      return
    tag = object.AddObserver(event, method)
    self.Observations.append([object, event, method, group, tag])

  def hasObserver(self, object, event, method):
    for o, e, m, g, t in self.Observations:
      if o == object and e == event and m == method:
        return True
    return False

  ###
  # Retriver Logic
  ###
  def evaluateDb(self, kmap, regenmat): # Calculate a dissimilarity matrix for leave-one-out MAP
    # Read in the log csv
    trans = self._readTrans()
    ntrans = len(trans)
    matpath = join(self.dbpath, 'DissimilarityMatrix')
    D = np.zeros((ntrans, ntrans)) # Pariwised Dissimilarity Matrix

    if regenmat:
      # For ith:n-1 successful transformation calculate its dissimilarity to (i+1)-th : n-th
      for i, t in enumerate(trans):
        # Load i-th image A (early) and image B (late)
        # Find Image A by its ID
        patha = self.find_file_with_imgid(t['IMAGEID-A'], join(self.dbpath, 'flirted'))
        # Find Image B by its ID
        pathb = self.find_file_with_imgid(t['IMAGEID-B'], join(self.dbpath, 'flirted'))

        slicer.util.loadVolume(patha)
        id1 = self._findimgid(patha)[0]
        v1 = slicer.util.getNode(pattern="*%s*" % id1)
        v1.SetName(id1)
        assert v1 != None

        slicer.util.loadVolume(pathb)
        id2 = self._findimgid(pathb)[0]
        v2 = slicer.util.getNode(pattern="*%s*" % id2)
        v2.SetName(id2)
        assert v2 != None

        # Apply transform j to image A and calculate D(trans(A), B) to be put in D(i, j)
        tname_i = t['IMAGEID-A'] + '-' + t['IMAGEID-B'] + '.h5'
        slicer.util.loadTransform(join(self.dbpath, 'trans', tname_i))
        tnode_i = slicer.util.getNode(pattern="*%s*" % tname_i[:-3])

        for j in xrange(i+1, len(trans)):
          #
          # The upper triangle of the matrix D
          #
          tname_j = trans[j]['IMAGEID-A'] + '-' + trans[j]['IMAGEID-B'] + '.h5'
          print "***********************************"
          print "Working on Matrix : %d, %d" % (i, j)
          print "Transform: %s" % tname_j
          print "***********************************"

          v1_copy = slicer.util.getNode('v1_copy')
          if v1_copy == None:
            v1_copy = slicer.vtkMRMLScalarVolumeNode()
            v1_copy.Copy(v1)
            v1_copy.SetName('v1_copy')
            scene.AddNode(v1_copy)

          v1_j_output = slicer.util.getNode('v1_j_output') 
          if v1_j_output == None:
            v1_j_output = slicer.vtkMRMLScalarVolumeNode()
            v1_j_output.SetName('v1_j_output')
            scene.AddNode(v1_j_output)


          # Apply transform j to image A and calculate D(trans(A), B) to be put in D(i, j)
          slicer.util.loadTransform(join(self.dbpath, 'trans', tname_j))
          tnode_j = slicer.util.getNode(pattern="*%s*" % tname_j[:-3])
          assert tnode_j != None, 'transform %s not found' % tname_j[:-3]
          self.resample(v1_copy, tnode_j, v1_j_output) # Wait for completion
          while(self.CLINode.GetStatus()!=self.CLINode.Completed): pass 
          assert v1_copy.GetImageData() != None
          assert v1_j_output.GetImageData() != None
          assert v2!=None

          d = self.voldiff(v1_j_output, v2, 'mse') # Difference between v2 and the transformed v1
          D[i][j] = d

          #
          # The lower triangle of the matrix D
          #
          print "***********************************"
          print "Working on Matrix : %d, %d" % (j, i)
          print "Transform: %s" % tname_i
          print "***********************************"

          # Load i-th image A (early) and image B (late)
          # Find Image A by its ID
          patha_j = self.find_file_with_imgid(trans[j]['IMAGEID-A'], join(self.dbpath, 'flirted'))
          # Find Image B by its ID
          pathb_j = self.find_file_with_imgid(trans[j]['IMAGEID-B'], join(self.dbpath, 'flirted'))

          slicer.util.loadVolume(patha_j)
          id1_j = self._findimgid(patha_j)[0]
          v1_j = slicer.util.getNode(pattern="*%s*" % id1_j)

          slicer.util.loadVolume(pathb_j)
          id2_j = self._findimgid(pathb_j)[0]
          v2_j = slicer.util.getNode(pattern="*%s*" % id2_j)

          v1_i_output = slicer.util.getNode('v1_i_copy')
          if v1_i_output == None:
            v1_i_output = slicer.vtkMRMLScalarVolumeNode()
            v1_i_output.SetName('v1_i_copy')

          scene.AddNode(v1_i_output)

          # Apply transform j to image A and calculate D(trans(A), B) to be put in D(i, j)
          assert tnode_i != None, 'transform %s not found' % tname_i[:-3]
          self.resample(v1_j, tnode_i, v1_i_output) # Wait for completion
          while(self.CLINode.GetStatus() != self.CLINode.Completed): pass 
          assert v2_j.GetImageData() != None
          assert v1_i_output.GetImageData() != None

          d = self.voldiff(v1_i_output, v2_j, 'mse') # Difference between v2 and the transformed v1
          D[j][i] = d

          # Clean the temporary nodes

          scene.RemoveNode(tnode_j)
          scene.RemoveNode(v1_j)
          scene.RemoveNode(v2_j)
          print D

        scene.RemoveNode(v1)
        scene.RemoveNode(v2)
        scene.RemoveNode(tnode_i)

      # Save dissimilarity matrix 
      np.save(matpath, D)
    else:
      print "Loading Dissimilarity Matrix from file: %s" % matpath
      D = np.load(matpath+'.npy', dtype=float)

    print 'Dissimilarity Matrix', D

    # TODO:
    # Sort the similarity or transform i
    # Calculate MAP based on the dissimilarity matrix
    # Return MAP results
    return 0

  def resample(self, inputv, trans, outputv):
    parameters = {}
    # Setting the parameters for the BRAINS RESAMPLE CLI
    parameters["inputVolume"] = inputv
    parameters["outputVolume"] = outputv
    parameters["pixelType"] = 'float'
    parameters["deformationVolume"] = trans 
    parameters["interpolationMode"] = 'WindowedSinc'
    parameters["defaultValue"] = '0'
    parameters["numberOfThreads"] = str(multiprocessing.cpu_count()) 

    # Run BRAINS Resample CLI
    resamplecli = self.getCLINode(slicer.modules.brainsresample)
    self.addObserver(resamplecli, self.StatusModifiedEvent,\
                                  self.onFinishResample)
    #self.resample_sema.acquire()
    #print 'sema acqured by cli'
    resamplenode = slicer.cli.run(slicer.modules.brainsresample,\
                                  resamplecli, parameters, wait_for_completion=True)

  def onFinishResample(self, cliNode, event):
    if not cliNode.IsBusy():
      self.removeObservers(self.onFinishResample)

    print("Got a %s from a %s" % (event, cliNode.GetClassName()))
    if cliNode.IsA('vtkMRMLCommandLineModuleNode'):
      print("Status is %s" % cliNode.GetStatusString())
      if cliNode.GetStatusString() == 'Completed':
        self.CLINode.SetStatus(self.CLINode.Completed)
        print 'resample completed'
        #self.resample_sema.release()
      else:
        self.CLINode.SetStatus(cliNode.GetStatus())
        print 'fuck', cliNode.GetStatusString()

  def voldiff(self, v1, v2, type='mse'):
    # See if both volumes can be found in the scene
    v1inscene = slicer.util.getNode(pattern="*%s*" % v1.GetName())
    v2inscene = slicer.util.getNode(pattern="*%s*" % v2.GetName())
    '''
    assert v1inscene != None
    assert v2inscene != None
    assert v1inscene.GetImageData() != None
    assert v2inscene.GetImageData() != None
    '''

    if type == 'mse':
      m1 = slicer.util.array(v1inscene.GetName())
      m2 = slicer.util.array(v2inscene.GetName())
      e = ((m1 - m2) ** 2).mean(axis=None)
    else:
      raise NotImplementedError()
    return e

  def _readTrans(self):
    trans = [] #< Header: [values]>
    with open(join(self.dbpath, 'trans', 'demonlog.csv')) as f:
      reader = csv.reader(f)
      header = reader.next()

      for row in reader:
        t = {}
        for col, h in enumerate(header):
          t[h] = row[col]
        trans.append(t)
    
    return [t for t in trans if t['Status'] == 'Success'] # Ignore the failed cases

  def findtransname(self, path):
    return os.path.split(path)[1].split('.')[0]


class AdniDemonsDatabaseTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  setuped = False

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    #slicer.mrmlScene.Clear(0)
    #self.dbpath = join(os.path.dirname(os.path.realpath(__file__)), 'Testing', '4092cMCI-GRAPPA2')
    self.dbpath = join(os.path.dirname(os.path.realpath(__file__)), 'Testing', '5ADNI-Patients')
    self.logic = AdniDemonsDatabaseLogic(self.dbpath)
    self.flirttemplatepath = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain.nii.gz'
    self.setuped = True

  def runTest(self, scenario="all"):
    """Run as few or as many tests as needed here.
    """
    start = time.time()
    self.setUp()
    if scenario == "all":
      self.test_dbgen()
      self.test_betandflirt()
      #self.test_demonregister()
      self.test_demonsall()
      self.test_single_resample()
    else:
      testmethod = getattr(self, scenario)
      testmethod()

    finish = time.time()
    eclp = finish - start
    print 'Testing Finished, Eclapsed: %f.2 mins' % ((finish - start) / 60)

  def test_dbgen(self):
    if not self.setuped:
      self.setUp()

    self.delayDisplay("Test Generate Database Sequence")
    self.logic.dbgen(join(self.dbpath, 'db.csv'))

  def test_betandflirt(self):
    if not self.setuped:
      self.setUp()
    self.delayDisplay("Test bet and flirt")
    self.logic.betandflirtall(self.flirttemplatepath, 0.3)

  def test_demonregister(self):
    if not self.setuped:
      self.setUp()

    self.delayDisplay("Test Single Demons")
    # Provide two image files
    movingpath = 'ADNI_116_S_4092_MR_MPRAGE_GRAPPA2_br_raw_20110624151135946_18_S112543_I241691.flirted.nii.gz'
    fixedpath = 'ADNI_116_S_4092_MR_MPRAGE_GRAPPA2_br_raw_20120808132426064_33_S160153_I322535.flirted.nii.gz'
    movingpath = join(self.dbpath, 'flirted', movingpath)
    fixedpath = join(self.dbpath, 'flirted', fixedpath)
    self.logic.demonregister(fixedpath, movingpath)

    '''
    # After Demons registration see if the trans file exist
    assert(os.path.exists(join(os.path.realpath(__file__), 'Testing/4092cMCI-GRAPPA2/trans/241691-322535.h5')))

    # Read the trans file and the volumes back and apply the transform for visual check
    movingvol = slicer.util.loadVolume(join(self.logic.dbpath, movingpath))
    fixedvol = slicer.util.loadVolume(join(self.logic.dbpath, fixedpath))
    #trans = slicer.util.loadTransform(join(os.path.realpath(__file__), 'Testing/4092cMCI-GRAPPA2/trans/241691-322535.h5')))
    trans = slicer.vtkSlicerTransformLogic.AddTransform(join(os.path.realpath(__file__), 'Testing/4092cMCI-GRAPPA2/trans/241691-322535.h5'))
    slicer.vtkSlicerTransformLogic.hardenTransform(movingvol)
    '''

  def test_demonsall(self):
    if not self.setuped:
      self.setUp()
    self.delayDisplay("Test Multiple Demons")
    self.logic.demonsall(12)
    #self.logic.run()

  def test_single_resample(self):
    sourcepath = join(self.dbpath, 'flirted', 'ADNI_153_S_4133_MR_MT1__GradWarp__N3m_Br_20110804074614762_S116698_I248655.flirted.nii.gz')
    print sourcepath
    slicer.util.loadVolume(sourcepath)
    sourceid = self.logic._findimgid(sourcepath) [0]
    print sourceid
    inputv = slicer.util.getNode(pattern="*%s*" % sourceid)
    print 'inputv: ', type(inputv)

    outputv = slicer.vtkMRMLScalarVolumeNode()
    transpath = join(self.dbpath, 'trans', '248655-334104.h5')

    slicer.util.loadTransform(transpath)
    transname = self.logic.findtransname(transpath)
    trans = slicer.util.getNode(transname)

    scene.AddNode(inputv)
    scene.AddNode(outputv)
    scene.AddNode(trans)

    self.logic.resample(inputv, trans, outputv)

    return inputv, trans, outputv

  def test_volume_difference(self):
    inputv, trans, outputv = self.test_single_resample()

    targetpath = join(self.dbpath, 'flirted', 'ADNI_153_S_4133_MR_MT1__GradWarp__N3m_Br_20120913163551448_S159893_I334104.flirted.nii.gz')
    slicer.util.loadVolume(targetpath)
    targetid = self.logic._findimgid(targetpath)[0]
    targetv = slicer.util.getNode(pattern="*%s*" % targetid)
    scene.AddNode(targetv)

    inputdiff = self.logic.voldiff(inputv, targetv, 'mse')
    targetdiff = self.logic.voldiff(outputv, targetv, 'mse')
    print "Input Diff: %f\nTarget Diff: %f" % (inputdiff, targetdiff)
    assert inputdiff > targetdiff, "Registered difference is larger than unregistered difference\n"

  def test_evaluatedb(self):
    mAp = self.logic.evaluateDb(5, True)
    print 'MAP: %f' % mAp