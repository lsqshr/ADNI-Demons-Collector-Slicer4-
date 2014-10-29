import os
import re
import csv
import time
from collections import Counter
from threading import BoundedSemaphore
import unittest
import subprocess
import multiprocessing
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

class AdniDemonsCollector:
  def __init__(self, parent):
    parent.title        = "ADNI Demons  Collector"
    parent.categories   = ["Data Collector"]
    parent.dependencies = []
    parent.contributors = ["Siqi Liu (USYD), Sidong Liu (USYD, BWH), Sonia Pujol (BWH)"]
    parent.helpText     = """
    """
    parent.acknowledgementText = """
    """ 

    self.parent = parent

    # Add this test to the SelfTest module's list for discovery when the module
    # is created.  Since this module may be discovered before SelfTests itself,
    # create the list if it doesn't already exist.
    try:
      slicer.selfTests
    except AttributeError:
      slicer.selfTests = {}
    slicer.selfTests['AdniDemonsCollector'] = self.runTest

  def runTest(self):
    tester = AdniDemonsCollectorTest()
    tester.runTest()

#
# qAdniDemonsCollectorWidget
#

class AdniDemonsCollectorWidget(ScriptedLoadableModuleWidget):

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    self.dbpath = None
    self.dbcsvpath = None
    self.flirttemplate = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain.nii.gz' 

    # Instantiate and connect widgets ...

    #
    # Reload and Test area
    #
    reloadCollapsibleButton       = ctk.ctkCollapsibleButton()
    reloadCollapsibleButton.text  = "Reload && Test"
    self.layout.addWidget(reloadCollapsibleButton)
    reloadFormLayout              = qt.QFormLayout(reloadCollapsibleButton) 

    self.clearButton              = qt.QPushButton("Clear Scene")
    self.clearButton.toolTip      = "Clear all the volumes and models in 3D views"
    self.clearButton.name         = "AdniDemonsCollector Clear"
    reloadFormLayout.addWidget(self.clearButton)
    self.clearButton.connect('clicked()', self.onClear)

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadButton             = qt.QPushButton("Reload")
    self.reloadButton.toolTip     = "Reload AdniDemonsCollector"
    self.reloadButton.name        = "AdniDemonsCollector Reload"
    reloadFormLayout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked()', self.onReload)

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
    settingCollapsibleButton.text = "Settings"
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
    self.dbcsvpath = '' if self.dbButton.text.find(':') == -1 else os.path.join(self.dbpath, 'db.csv')
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
    self.demonscheck.enabled = False
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
    self.seqCombo.addItems(["All", "Stable: NL", "Stable: MCI", "Stable: AD", "NL2MCI", "MCI2AD"])
    settingFormLayout.addWidget(qt.QLabel("Sequence Type"), 6 ,0)
    settingFormLayout.addWidget(self.seqCombo, 6, 1)

    actionCollapsibleButton       = ctk.ctkCollapsibleButton()
    actionCollapsibleButton.text  = "Action"
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

    # Add vertical spacer
    self.layout.addStretch(1)

  # -------------------------------------
  def onClear(self):
    slicer.mrmlScene.Clear(0)

  # ----------------------------------------------
  def onReload(self, moduleName = "AdniDemonsCollector"): 
    """
    Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    import imp, sys, os, slicer

    widgetName = moduleName + "Widget"

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
    globals()[widgetName.lower()] = eval('globals()["%s"].%s(parent)' % (moduleName, widgetName))
    globals()[widgetName.lower()].setup()

  def onTestAll(self):
    self.onReload()
    test = AdniDemonsCollectorTest()
    test.runTest()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector.currentNode() and self.outputSelector.currentNode()

  def onApplyButton(self):
    logic = AdniDemonsCollectorLogic(self.dbpath)
    if self.betflirtcheck.checked == 1:
        logic.betandflirtall(self.flirttemplate, self.betflirtspin.getValue())

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
        self.dbcsvpath = os.path.join(self.dbpath, 'db.csv')
        #self._updateBtnTxt(self.csvButton, self.dbcsvpath)
        self.csvlabel.text = self.dbcsvpath

        # If ./betted or ./flirted exist in the dbpath, enable clear flirt button
        if os.path.exists(os.path.join(self.dbpath, 'betted')) or \
                os.path.exists(os.path.join(self.dbpath, 'betted')) :
            self.clearFlirtButton.enabled = True                

        # If db.csv exists, enable dbgen button
        if os.path.exists(os.path.join(self.dbpath, 'db.csv')):
            self.dbgenButton.enabled = True

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
        msgb = qt.QMessageBox();
        msgb.setText('Unknown DB path')
        msgb.setStandardButtons(qt.QMessageBox.Cancel)
        msgb.show() # .show() does not work. should make it .exec()
    else:
        logic = AdniDemonsCollectorLogic(self.dbpath)
        logic.dbgen(self.dbcsvpath)

  def onFlirtClear(self):
    logic = AdniDemonsCollectorLogic(self.dbpath)
    logic.clean()
#
# AdniDemonsCollectorLogic
#
class AdniDemonsCollectorLogic(ScriptedLoadableModuleLogic):
  def __init__(self, dbpath):
    maxthread = 1
    self.pool_sema = BoundedSemaphore(maxthread)
    self.dbpath = dbpath

  def _readcolumn(self, colname):
    limgid = []

    with open(os.path.join(self.dbpath, 'dbgen.csv')) as f:
        r = csv.reader(f)
        header = r.next()
        mididx = header.index(colname)

        for row in r:
            limgid.append(row[mididx])
         
    return limgid

  def _findimgid(self, fname):
    lmatch = re.findall('_I\d+', fname)
    assert(len(lmatch) <= 1, 'More than one matches were found: ')
    cleanmatch = [] 

    for m in lmatch: 
        cleanmatch.append(m[1:]) # Remove the '_' before image id 

    return cleanmatch

  def dbgen(self, dbcsvpath):
    safedbpath = self.dbpath.replace(' ', '\ ')
    safecsvpath = dbcsvpath.replace(' ', '\ ')
    if os.path.exists(safecsvpath):
        os.system("Rscript %s %s %s" % (os.path.join(os.path.dirname(os.path.realpath(__file__)),\
                     'dbgen.r'), safedbpath, safecsvpath))
    else:
        print "db.csv not found."

  def _traverseForImage(self, func):
    # Traverse the dbpath: if the image id is wanted, bet and flirt this image
    # Only the flirted image will be saved in self.dbpath/flirted/IMAGEID.nii
    for root, dirs, files in os.walk(self.dbpath):
        for file in files:
            imgid = self._findimgid(file)
            func(root, file, imgid)

  def betandflirtall(self, flirttemplate, betthreshold):
    start = time.time()
    imgctr = Counter(hit=0)
    # read in the csv and extract the image ids to be done
    limgid = self._readcolumn('Image.Data.ID')

    bettedpath = os.path.join(self.dbpath, 'betted')
    flirtedpath = os.path.join(self.dbpath, 'flirted')

    if not os.path.exists(bettedpath):
        os.makedirs(bettedpath)

    if not os.path.exists(flirtedpath):
        os.makedirs(flirtedpath)

    # Traverse the dbpath: if the image id is wanted, bet and flirt this image
    # Only the flirted image will be saved in self.dbpath/flirted/IMAGEID.nii
    def betandflirt(root, file, imgid, limage):
        f, ext = os.path.splitext(file)
        if len(imgid) > 0:
            if ext == '.nii' and imgid[0].replace('I','') in limgid:
                imgctr['hit'] += 1
                print 'flirting %s' % file
                imgpath = os.path.join(root, file)
                roiimgpath = os.path.join(bettedpath, f)
                subprocess.call(['standard_space_roi', imgpath, roiimgpath, '-b'], shell=False)
                bettedimgpath = os.path.join(bettedpath, f+'.betted.nii')
                subprocess.call(['bet', os.path.join(bettedpath, f), bettedimgpath, '-f', str(betthreshold)], shell=False)
                subprocess.call(['rm', roiimgpath+'.nii.gz'])
                print 'flirtedpath:' , flirtedpath
                flirtimgpath = os.path.join(flirtedpath, f + '.flirted.nii')   
                print 'flirtimgpath: ', flirtimgpath
                subprocess.call(['flirt', '-ref', flirttemplate, '-in', bettedimgpath, '-out', flirtimgpath])
    self._traverseForImage(lambda root, file, imgid: betandflirt(root, file, imgid, limgid))
    end = time.time()
    print '*** finished betandflirt ***'
    print 'Total Elapsed Time: %f.2\tAverage Time For Each Image: %f.2' % (end-start, (end-start)/imgctr['hit'])

  # Delete the generated processing results 
  def clean(self):
    subprocess.call(['rm', '-rf', os.path.join(self.dbpath, 'betted'), os.path.join(self.dbpath, 'flirted')])

  def run(self):
    fixedfile = 'ADNI_116_S_4092_MR_MPRAGE_GRAPPA2_br_raw_20120118092234173_73_S137148_I278831.nii.flirted.nii.gz'
    movingfile = 'ADNI_116_S_4092_MR_MPRAGE_GRAPPA2_br_raw_20110624151135946_18_S112543_I241691.nii.flirted.nii.gz'
        
    start = time.time()
    for i in range(5):
        #self.pool_sema.acquire()
        print 'running %d' % i
        self.demonregister(dbpath, fixedfile, movingfile)
    avgtime = (time.time() - start) / 5
    print "Averge Running Time: %f.2" % avgtime

  def demonregister(self, dbpath, fixedfile, movingfile):
    slicer.util.loadVolume(os.path.join(dbpath, 'flirted', fixedfile)) # Load fixed volume
    slicer.util.loadVolume(os.path.join(dbpath, 'flirted', movingfile)) # Load moving Volume

    fixedvol = slicer.util.getNode(pattern="*%s*" % self._findimgid(fixedfile))
    movingvol = slicer.util.getNode(pattern="*%s*" % self._findimgid(movingfile))

    # Create Output Volume if it does not exist
    outputvol = slicer.util.getNode('outputvol') 
    if outputvol is None:
        outputvol = slicer.vtkMRMLScalarVolumeNode()
        outputvol.SetName('outputvol')
        slicer.mrmlScene.AddNode(outputvol)
        assert(slicer.util.getNode('outputvol') is not None )

    gridtransnode = slicer.util.getNode('gridtrans')
    if gridtransnode is None:
        gridtransnode = slicer.vtkMRMLGridTransformNode() 
        gridtransnode.SetName('gridtrans')
        slicer.mrmlScene.AddNode(gridtransnode)
        assert(slicer.util.getNode('gridtrans') is not None )

    # Set parameters    
    parameters = {}
    parameters['fixedVolume'] = fixedvol.GetID()
    parameters['movingVolume'] = movingvol.GetID()
    parameters['outputVolume'] = outputvol.GetID()
    parameters['outputDisplacementFieldVolume'] = gridtransnode.GetID() 
    parameters['inputPixelType'] = 'float'
    parameters['outputPixelType'] = 'float'
    parameters['interpolationMode'] = 'Linear'
    parameters['registrationFilterType'] = 'Diffeomorphic'
    parameters['smoothDisplacementFieldSigma'] = '1'
    parameters['numberOfPyramidLevels'] = '5'
    parameters['numberOfPyramidLevels'] = '5'
    parameters['minimumFixedPyramid']   = '16,16,16'
    parameters['minimumMovingPyramid']  = '16,16,16'
    parameters['arrayOfPyramidLevelIterations'] = '300,50,30,20,15'
    parameters['numberOfHistogramBins'] = '256'
    parameters['numberOfMatchPoints'] = '2' 
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
    parameters['numberOfThreads'] = str(multiprocessing.cpu_count()*2)

    # Run Demons Registration CLI
    demonscli = slicer.modules.brainsdemonwarp

    def releaseSema(caller, event):
      print("Got a %s from a %s" % (event, caller.GetClassName()))
      if caller.IsA('vtkMRMLCommandLineModuleNode'):
        print("Status is %s" % caller.GetStatusString())

        #if caller.GetStatusString() == 'Completed':
        #  print 'Lock is released=================================='
          #self.pool_sema.release() 

    demonnode = slicer.cli.run(demonscli, None, parameters, wait_for_completion=True)
    demonnode.AddObserver('ModifiedEvent', releaseSema)
    return True

class AdniDemonsCollectorTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)
    self.dbpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'Testing', '4092cMCI-GRAPPA2')
    self.logic = AdniDemonsCollectorLogic(self.dbpath)
    self.flirttemplatepath = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain.nii.gz'

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_dbgen()
    self.test_betandflirt()

  def test_dbgen(self):
    self.delayDisplay("Test Generate Database Sequence")
    self.logic.dbgen(os.path.join(self.dbpath, 'db.csv'))

  def test_betandflirt(self):
    self.delayDisplay("Test Generate Database Sequence")
    self.logic.betandflirtall(self.flirttemplatepath, 0.3)
