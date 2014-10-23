import os
import re
import time
from threading import BoundedSemaphore
import unittest
import multiprocessing
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
'''
slicer:0x7f7318284cb0 --processinformationaddress 0x8e51250 --movingVolume slicer:0x1eafcc0#vtkMRMLScalarVolumeNode2 
--fixedVolume slicer:0x1eafcc0#vtkMRMLScalarVolumeNode4 --inputPixelType float --outputPixelType float --interpolationMode Linear 
--registrationFilterType Diffeomorphic --smoothDisplacementFieldSigma 1 --numberOfPyramidLevels 5 --minimumFixedPyramid 16,16,16 
--minimumMovingPyramid 16,16,16 --arrayOfPyramidLevelIterations 300,50,30,20,15 --numberOfHistogramBins 256 --numberOfMatchPoints 2 
--medianFilterSize 0,0,0 --maskProcessingMode NOMASK --lowerThresholdForBOBF 0 --upperThresholdForBOBF 70 --backgroundFillValue 0 
--seedForBOBF 0,0,0 --neighborhoodForBOBF 1,1,1 --outputDisplacementFieldPrefix none --checkerboardPatternSubdivisions 4,4,4 --gradient_type 0 
--upFieldSmoothing 0 --max_step_length 2 --numberOfBCHApproximationTerms 2 --numberOfThreads -1 
'''

#
# JustDemons
#

class JustDemons(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "JustDemons" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Examples"]
    self.parent.dependencies = []
    self.parent.contributors = ["Jean-Christophe Fillion-Robin (Kitware), Steve Pieper (Isomics)"] # replace with "Firstname Lastname (Org)"
    self.parent.helpText = """
    This is an example of scripted loadable module bundled in an extension.
    """
    self.parent.acknowledgementText = """
    This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc. and Steve Pieper, Isomics, Inc.  and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

#
# qJustDemonsWidget
#

class JustDemonsWidget(ScriptedLoadableModuleWidget):

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

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
    self.clearButton.name         = "MosaicViewer Clear"
    reloadFormLayout.addWidget(self.clearButton)
    self.clearButton.connect('clicked()', self.onClear)

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadButton             = qt.QPushButton("Reload")
    self.reloadButton.toolTip     = "Reload JustDemons"
    self.reloadButton.name        = "JustDemons Reload"
    reloadFormLayout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked()', self.onReload)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = True 
    reloadFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)

    # Add vertical spacer
    self.layout.addStretch(1)

  # -------------------------------------
  def onClear(self):
    slicer.mrmlScene.Clear(0)

  # ----------------------------------------------
  def onReload(self, moduleName = "JustDemons"): 
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
    logic = JustDemonsLogic()
    print("Run the algorithm")
    logic.run()


#
# JustDemonsLogic
#

class JustDemonsLogic(ScriptedLoadableModuleLogic):
  def __init__(self):
    maxthread = 1
    self.pool_sema = BoundedSemaphore(maxthread)

  def _findimgid(self, fname):
    lmatch = re.findall('_I\d+', fname)
    assert(len(lmatch) == 1)
    return (lmatch[0])[1:]

  def run(self):
    dbpath = '/home/siqi/Desktop/4092cMCI-GRAPPA2'

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

class JustDemonsTest(ScriptedLoadableModuleTest):
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
    self.test_JustDemons1()

  def test_JustDemons1(self):
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
    logic = JustDemonsLogic()
    self.assertTrue( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
