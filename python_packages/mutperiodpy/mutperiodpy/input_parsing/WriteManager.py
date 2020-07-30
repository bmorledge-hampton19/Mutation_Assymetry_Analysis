# This script contains a class for managing the writing of input data to various stratified data files.
# Once set up, it only needs to be passed data one line at a time.

import os
from typing import IO
from mutperiodpy.helper_scripts.UsefulFileSystemFunctions import (Metadata, checkDirs, dataTypes, generateFilePath,
                                                                  generateMetadata, getIsolatedParentDir)
from mutperiodpy.input_parsing.IdentifyMSI import MSIIdentifier


class WriteManager:

    def __init__(self, rootDataDir):

        # Get the metadata from the given directory
        self.rootDataDir = rootDataDir
        self.rootMetadata = Metadata(self.rootDataDir)

        # create and open the output file in the same directory as the root data.
        rootOutputFilePath = generateFilePath(directory = self.rootDataDir, dataGroup = self.rootMetadata.dataGroupName,
                                              context = "singlenuc", dataType = dataTypes.mutations, fileExtension = ".bed")
        self.rootOutputFile = open(rootOutputFilePath, 'w')

        # By default, all other write options are off unless otherwise specified.
        self.stratifyByIndividualCohorts = False
        self.stratifyByMS = False
        self.stratifyBySignature = False


    # Create the necessary functions to use the class with the "with" keyword.
    def __enter__(self): return self
    
    def __exit__(self, type, value, tb):

        # Close all opened files.
        self.cleanup()


    # Prepares the manager to separate data by cohort.
    def setUpForIndividualCohorts(self):

        self.stratifyByIndividualCohorts = True

        self.currentIndividualCohortID = None # The cohort being written to at a point in time.
        self.currentIndividualCohortFile: IO = None # The open file for the current cohort.
        self.completedIndividualCohorts = dict() # A hashtable of cohorts that have been seen before and should NOT be revisited/rewritten.        

        # Create the directory.
        self.rootIndividualCohortsDirectory = os.path.join(self.rootMetadata.directory,"individual_cohorts")
        checkDirs(self.rootIndividualCohortsDirectory)


    # Open a new individual cohort file for writing (and close the last one, if applicable.)
    def setUpNewIndividualCohort(self, cohortID):

        if self.currentIndividualCohortFile is not None: self.currentIndividualCohortFile.close()

        # Make sure this is actually a new cohort.
        if cohortID in self.completedIndividualCohorts:
            raise ValueError("The cohort " + cohortID + " was encountered in more than one distinct block of data.")
        else:
            self.currentIndividualCohortID = cohortID

        individualCohortDirectory = os.path.join(self.rootIndividualCohortsDirectory,self.currentIndividualCohortID)
        individualCohortDataGroup = self.currentIndividualCohortID + "_" + self.rootMetadata.dataGroupName

        checkDirs(individualCohortDirectory)

        # Determine which other set up "umbrella" cohorts this cohort belongs to.
        cohortMembership = [self.currentIndividualCohortID,]
        if self.stratifyByMS:
            if self.currentIndividualCohortID in self.MSICohorts:
                cohortMembership.append("MSI")
            else:
                cohortMembership.append("MSS")
        # TODO: determine mutsig membership if requested


        # Generate the file path and metadata file and open the file for writing.
        individualCohortFilePath = generateFilePath(directory = individualCohortDirectory, dataGroup = individualCohortDataGroup, 
                                                    context = "singlenuc", dataType = dataTypes.mutations, fileExtension = ".bed")
        self.currentIndividualCohortFile = open(individualCohortFilePath, 'w')
        generateMetadata(individualCohortDataGroup, self.rootMetadata.genomeName, self.rootMetadata.nucPosName,
                         os.path.join("..",self.rootMetadata.localParentDataPath), individualCohortDirectory, *cohortMembership)


    # Prepares the manager to separate cohorts by microsatellite stability.
    # Returns an MSIIdentifier object to be "completed" by the function caller.
    def setUpForMSStratification(self) -> MSIIdentifier:

        self.stratifyByMS = True

        self.MSICohorts = dict() # A hashtable of individual cohorts with MSI

        # Create the necessary directories, file paths, and metadata.
        aggregateMSDirectory = os.path.join(self.rootMetadata.directory,"microsatellite_analysis")
        aggregateMSSDirectory = os.path.join(aggregateMSDirectory,"MSS")
        aggregateMSIDirectory = os.path.join(aggregateMSDirectory,"MSI")
        checkDirs(aggregateMSSDirectory, aggregateMSIDirectory)

        generateMetadata("MSS_" + self.rootMetadata.dataGroupName, self.rootMetadata.genomeName, self.rootMetadata.nucPosName,
                         os.path.join('..','..',self.rootMetadata.localParentDataPath), aggregateMSSDirectory, "MSS")
        generateMetadata("MSI_" + self.rootMetadata.dataGroupName, self.rootMetadata.genomeName, self.rootMetadata.nucPosName,
                         os.path.join('..','..',self.rootMetadata.localParentDataPath), aggregateMSIDirectory, "MSI")

        aggregateMSSFilePath = generateFilePath(directory = aggregateMSSDirectory, dataGroup = "MSS_" + self.rootMetadata.dataGroupName,
                                                context = "singlenuc", dataType = dataTypes.mutations, fileExtension = ".bed")
        self.aggregateMSSFile = open(aggregateMSSFilePath, 'w')
        aggregateMSIFilePath = generateFilePath(directory = aggregateMSIDirectory, dataGroup = "MSI_" + self.rootMetadata.dataGroupName,
                                                context = "singlenuc", dataType = dataTypes.mutations, fileExtension = ".bed")
        self.aggregateMSIFile = open(aggregateMSIFilePath, 'w')

        # Set up the MSIIdentifier to be returned.
        intermediateFilesDir = os.path.join(self.rootDataDir,"intermediate_files")
        checkDirs(intermediateFilesDir)
        MSISeqInputDataFilePath = generateFilePath(directory = intermediateFilesDir, dataGroup = self.rootMetadata.dataGroupName,
                                                   dataType = "MSISeq_data", fileExtension = ".txt")
        self.MSICohortsFilePath = generateFilePath(directory = self.rootIndividualCohortsDirectory, dataGroup = self.rootMetadata.dataGroupName, 
                                                   dataType = "MSI_cohorts", fileExtension = ".txt")

        self.myMSIIdentifier = MSIIdentifier(MSISeqInputDataFilePath, self.MSICohortsFilePath)
        return(self.myMSIIdentifier)


    # TODO: set up signature stratification


    # Writes the given data to all the relevant files based on how the manager was set up.
    def writeData(self, chromosome, startPos, endPos, mutFrom, alteration, strand, cohortID = '.'):

        outputLine = '\t'.join((chromosome, startPos, endPos, mutFrom, alteration, strand)) + '\n'

        # Write data to the root output file.
        self.rootOutputFile.write(outputLine)

        # Write to microsatellite designation if it was set up.
        if self.stratifyByMS and cohortID != '.':

            # Make sure the MSICohorts hashtable has actually been propogated.
            if len(self.MSICohorts) == 0:
                if not self.myMSIIdentifier.MSICohortsIdentified:
                    raise ValueError("MSIIdentifier protocol was never completed.")
                else:
                    with open(self.MSICohortsFilePath, 'r') as MSICohortsFile:
                        for line in MSICohortsFile:
                            self.MSICohorts[line.strip()] = None

            if cohortID in self.MSICohorts:
                self.aggregateMSIFile.write(outputLine)
            else:
                self.aggregateMSSFile.write(outputLine)

        # TODO: Write to signature designations if it was set up.

        # Write to individual cohorts as desired.
        if self.stratifyByIndividualCohorts and cohortID != '.':
            
            # Check to see if we've reached a new cohortID .
            if self.currentIndividualCohortID is None or self.currentIndividualCohortID != cohortID:
                self.completedIndividualCohorts[self.currentIndividualCohortID] = None
                self.setUpNewIndividualCohort(cohortID)

            # Write to the current individual cohort.
            self.currentIndividualCohortFile.write(outputLine)


    # Closes open files to clean up the class after it's done being used.
    def cleanup(self):

        self.rootOutputFile.close()

        if self.stratifyByMS:
            self.aggregateMSIFile.close()
            self.aggregateMSSFile.close()

        # TODO: Close mutsig files.

        if self.stratifyByIndividualCohorts and self.currentIndividualCohortFile is not None:
            self.currentIndividualCohortFile.close()