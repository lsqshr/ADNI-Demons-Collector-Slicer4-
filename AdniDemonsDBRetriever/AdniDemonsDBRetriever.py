import os
from sets import Set
from os.path import join
import re
import csv
import time
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

class AdniDemonsDBRetriever:
  def __init__(self, parent):
    parent.title        = "ADNI Demons Retriever"
    parent.categories   = ["ADNI Demons DB"]
    parent.dependencies = []
    parent.contributors = ["Siqi Liu (USYD), Sidong Liu (USYD, BWH)"]
    parent.helpText     = """
    """
    parent.acknowledgementText = """
    """ 

    self.parent = parent


    # Add this test to the SelfTest module's list for discovery when the module
    # is created. Since this module may be discovered before SelfTests itself,
    # create the list if it doesn't already exist.
    try:
      slicer.selfTests
    except AttributeError:
      slicer.selfTests = {}
      slicer.selfTests['AdniDemonsDBRetriever'] = self.runTest

  def runTest(self):
      tester = AdniDemonsDBRetrieverTest()
      tester.runTest()

#
# qAdniDemonsDBRetrieverWidget
#

class AdniDemonsDBRetrieverWidget(ScriptedLoadableModuleWidget):

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
    self.clearButton.name         = "AdniDemonsDBRetriever Clear"
    reloadFormLayout.addWidget(self.clearButton)
    self.clearButton.connect('clicked()', self.onClear)

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadButton             = qt.QPushButton("Reload")
    self.reloadButton.toolTip     = "Reload AdniDemonsDBRetriever"
    self.reloadButton.name        = "AdniDemonsDBRetriever Reload"
    reloadFormLayout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked()', self.onReload)

    #
    # Testing Ariea
    #
    testCollapsibleButton       = ctk.ctkCollapsibleButton()
    testCollapsibleButton.text  = "Reload && Test"
    self.layout.addWidget(testCollapsibleButton)
    testLayout              = qt.QFormLayout(testCollapsibleButton) 

    # Get the test methods create a button for each of them
    testklsdir = dir(AdniDemonsDBRetrieverTest)
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
    testLayout.addWidget(self.testallButton)
    self.testallButton.connect('clicked()', self.onTestAll)

    #
    # Evaluate DB Area
    #
    evaluateCollapsibleButton      = ctk.ctkCollapsibleButton()
    evaluateCollapsibleButton.text = "Evaluate DB"
    self.layout.addWidget(evaluateCollapsibleButton)
    settingFormLayout             = qt.QGridLayout(evaluateCollapsibleButton) 

    #
    # DB Directory Selection Button
    #
    self.dbButton                 = qt.QPushButton("Set ADNI Database Directory")
    self.dbButton.toolTip         = "Set ANDI Database Directory. Assume in this folder, you have already generated a database with ADNI Demons DB Creator"
    self.dbButton.enabled         = True 
    settingFormLayout.addWidget(self.dbButton, 0, 0)
    self.dblabel = qt.QLabel(self.dbpath if self.dbpath != None else 'Empty')
    settingFormLayout.addWidget(self.dblabel, 0, 1)
    self.dbButton.connect('clicked(bool)', lambda: self.onFileButton('db'))
    
    #
    # Bet & Flirt Threshold
    #
    self.betflirtspin = qt.QDoubleSpinBox()
    self.betflirtspin.setRange(0.0, 10.0)
    self.betflirtspin.setSingleStep(1.0)
    self.betflirtspin.setValue(5)
    settingFormLayout.addWidget(qt.QLabel("K value for MAP"), 1 ,0)
    settingFormLayout.addWidget(self.betflirtspin, 1, 1)

    #
    # DB Evaluate Button
    #
    self.evaluateDbButton = qt.QPushButton('Evaluate DB')
    

    #
    # Show a Return Message
    #
    self.returnMsg = qt.QLabel("Ready") 
    actionFormLayout.addRow(self.returnMsg)

    # Add vertical spacer
    self.layout.addStretch(1)

  # -------------------------------------
  def onClear(self):
    slicer.mrmlScene.Clear(0)

  # ---------------------------------------------
  def onReloadAndTest(self, moduleName = "AdniDemonsDBRetriever", scenario = None):
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
  def onReload(self, moduleName = "AdniDemonsDBRetriever"): 
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
    test = AdniDemonsDBRetrieverTest()
    test.runTest()

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector.currentNode() and self.outputSelector.currentNode()

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

#
# AdniDemonsDBRetrieverLogic
#
class AdniDemonsDBRetrieverLogic(ScriptedLoadableModuleLogic):
  def __init__(self, dbpath):
    maxthread = 1
    self.dbpath = dbpath


class AdniDemonsDBRetrieverTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  setuped = False

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)
    #self.dbpath = join(os.path.dirname(os.path.realpath(__file__)), 'Testing', '4092cMCI-GRAPPA2')
    self.dbpath = join(os.path.dirname(os.path.realpath(__file__)), '../AdniDemonsDBCreator/Testing', '5ADNI-Patients')
    self.logic = AdniDemonsDBRetrieverLogic(self.dbpath)
    self.flirttemplatepath = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain.nii.gz'
    self.setuped = True

  def runTest(self, scenario="all"):
    """Run as few or as many tests as needed here.
    """
    start = time.time()
    self.setUp()

    if scenario == "all":
      pass
    else:
      testmethod = getattr(self, scenario)
      testmethod()
    finish = time.time()
    eclp = finish - start
    print 'Testing Finished, Eclapsed: %f.2 mins' % ((finish - start) / 60)
