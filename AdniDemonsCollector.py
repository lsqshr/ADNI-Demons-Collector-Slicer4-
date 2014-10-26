import os
import re
import time
from threading import BoundedSemaphore
import unittest
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
    This module creates mosaic views of multiple scene views
    """
    parent.acknowledgementText = """
    This module was developed by Siqi Liu, University of Sydney, Sidong Liu, University of Sydney and Brigham and Women's
    Hospital, and Sonia Pujol, Brigham and Women's Hospital, and was partially supported by ARC, AADRF, NIH NA-MIC
    (U54EB005149) and NIH NAC (P41EB015902).
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
    self.dbButton.connect('clicked(bool)', self.onDbButton)

    #
    # DB csv file Selection Button
    #
    csvbtntxt = "Set *.csv File For DB Record"
    self.dbcsvpath = '' if self.dbButton.text.find(':') == -1 else os.path.join(self.dbpath, 'db.csv')
    self.csvButton                 = qt.QPushButton(csvbtntxt if len(self.dbcsvpath) == 0 else csvbtntxt + ' : ' + self.dbcsvpath)
    self.csvButton.toolTip         = "Set ANDI Database Directory"
    self.csvButton.enabled         = True 
    settingFormLayout.addWidget(self.csvButton, 0, 1)
    self.csvButton.connect('clicked(bool)', self.oncsvButton)

    #
    # Bet & Flirt Threshold
    #
    self.betflirtspin = qt.QDoubleSpinBox()
    #self.betflirtspin.text = "Bet Threshold"
    self.betflirtspin.setRange(0.0, 1.0)
    self.betflirtspin.setSingleStep(0.05)
    self.betflirtspin.setValue(0.2)
    settingFormLayout.addWidget(qt.QLabel("Bet Threashold"), 1 ,0)
    settingFormLayout.addWidget(self.betflirtspin, 1, 1)

    #
    # Checkbox for Bet & Flirt
    #
    self.betflirtcheck = qt.QCheckBox("Run Bet + Flirt")
    self.betflirtcheck.setToolTip("Only the image IDs listed in the csv file will be processed. flirted images will be saved in path/to/db/flirted")
    self.betflirtcheck.checked = 0;
    settingFormLayout.addWidget(self.betflirtcheck, 2, 0)

    #
    # Checkbox for Running Demons Registration 
    #
    self.demonscheck = qt.QCheckBox("Run Demons")
    self.demonscheck.setToolTip("Only the image IDs listed in the csv file will be processed. Image sources will only be retrieved from path/to/db/flirted")
    self.demonscheck.checked = 0;
    settingFormLayout.addWidget(self.demonscheck, 2, 1)

    #
    # Interval Selection : 6m | 12m
    #
    self.intervalCombo = qt.QComboBox()
    self.intervalCombo.addItem("6 Month")
    self.intervalCombo.addItem("12 Month")
    settingFormLayout.addWidget(qt.QLabel("Extract Interval"), 3 ,0)
    settingFormLayout.addWidget(self.intervalCombo,3, 1)

    #
    # Sequence Label Selection: All, Stable: NL, Stable: MCI, Stable: AD, NL2MCI, MCI2AD 
    #
    self.seqCombo = qt.QComboBox()
    self.seqCombo.addItems(["All", "Stable: NL", "Stable: MCI", "Stable: AD", "NL2MCI", "MCI2AD"])
    settingFormLayout.addWidget(qt.QLabel("Sequence Type"), 4 ,0)
    settingFormLayout.addWidget(self.seqCombo,4, 1)

    actionCollapsibleButton       = ctk.ctkCollapsibleButton()
    actionCollapsibleButton.text  = "Action"
    self.layout.addWidget(actionCollapsibleButton)
    actionFormLayout              = qt.QFormLayout(actionCollapsibleButton) 

    #
    # Generate Database csv
    #
    self.dbgenButton = qt.QPushButton("Generate Database Sequence csv")
    self.dbgenButton.toolTip = "Generate A csv with required fields by merging the image collection csv and the dxsum. To make this button functional, pls make sure R language is installed in your system and \'RScript\' is in the $PATH."
    self.dbgenButton.enabled = True 
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

    # connections

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

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector.currentNode() and self.outputSelector.currentNode()

  def onApplyButton(self):
    logic = AdniDemonsCollectorLogic()
    logic.run()

  def onDbButton(self, type): # 'db'/'csv'
    dbDialog = qt.QFileDialog()
    dbDialog.setFileMode(2 if 'db' else 1)
    if type == 'db':
        self.dbpath = dbDialog.getExistingDirectory()
        btntxt = self.dbButton.text
        splt = btntxt.find(':')
        self.dbButton.text = btntxt + " : " + "\"%s\"" % self.dbpath if splt == -1 else btntxt[:splt + 2] + "\"%s\"" % self.dbpath
        self.dbcsvpath = '' if self.dbButton.text.find(':') == -1 else os.path.join(self.dbpath, 'db.csv')
    else type == 'csv':
        self.dbcsvpath = dbDialog.getExistingDirectory()

    csvbtntxt = self.csvButton.text
    splt = csvbtntxt.find(':')
    self.csvButton.text = csvbtntxt + " : " + "\"%s\"" % self.dbcsvpath if splt == -1 else csvbtntxt[:splt + 2]  + "\"%s\"" % self.dbcsvpath

  def onDbgenButton(self):
    if self.dbpath is None or self.dbcsvpath is None:
        msgb = qt.QMessageBox();
        msgb.setText('Unknown DB path')
        msgb.setStandardButtons(qt.QMessageBox.Cancel)
        msgb.show() # .show() does not work. should make it .exec()
    else:
        os.system("Rscript %s %s %s" % (os.path.join(os.path.dirname(os.path.realpath(__file__)),\
                     'dbgen.r'), self.dbpath, self.dbcsvpath))

#
# AdniDemonsCollectorLogic
#

class AdniDemonsCollectorLogic(ScriptedLoadableModuleLogic):
  def __init__(self):
    maxthread = 1
    self.pool_sema = BoundedSemaphore(maxthread)

  def _findimgid(self, fname):
    lmatch = re.findall('_I\d+', fname)
    assert(len(lmatch) == 1)
    return (lmatch[0])[1:]

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

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_AdniDemonsCollector1()

  def test_AdniDemonsCollector1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests sould exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        print('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        print('Loading %s...\n' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading\n')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = AdniDemonsCollectorLogic()
    self.assertTrue( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
