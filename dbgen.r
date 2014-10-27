options(echo=FALSE) # if you want see commands in output file

usePackage <- function(p) {
  if (!is.element(p, installed.packages()[,1]))
    install.packages(p, dep = TRUE)
  require(p, character.only = TRUE)
}

# Make a function to fill in the missing DXCHANGE for NA values
replacebyneighbour <- function(x){
  # For each NA value in this column replace it with its previous neighbour
  x[-length(x)] = na.locf(x, fromLast=TRUE)
  x = na.locf(x)
  return(x)
}

# Install ADNIMERGE library to use this script
# ADNIMERGE contains a dxsum table which has the DXCHANGE column filled for all subjects 
# Pre-requisite code:
#'''
usePackage("Hmisc") 
usePackage("R.matlab")
usePackage("zoo")

if (!is.element("ADNIMERGE", installed.packages()[,1]))
  install.packages("your/path/to/ADNIMERGE.tar.gz", repo=NULL, type="source")
require("ADNIMERGE", character.only = TRUE)

args <- commandArgs(trailingOnly = TRUE)
dbpath = args[1]
csvpath = args[2]
print(dbpath)
print(csvpath)
dbpath = "/home/siqi/Desktop/4092cMCI-GRAPPA2"
csvpath = "/home/siqi/Desktop/4092cMCI-GRAPPA2/db.csv"

dbcsv = read.csv(csvpath)
sub_adnimerge = subset(adnimerge, select=c("RID", "PTID", "VISCODE"));
sub_dxsum = subset(dxsum, select=c("RID", "VISCODE", "DXCHANGE"))
# add ptid to dxsum
dxsum_ptid = merge(dxsum, sub_adnimerge, by.x=c("RID", "VISCODE"), by.y=c("RID", "VISCODE"))

# Make MRI meta infomation table to convert find the visit code of the mri images
mrimetafields = c("RID","VISCODE","EXAMDATE")
submri15meta = subset(mrimeta, select=mrimetafields) # 1.5T
submrigometa = subset(mri3gometa, select=mrimetafields)
submri3meta  = subset(mri3meta, select=mrimetafields) 
submrimeta = rbind(submri15meta, submrigometa, submri3meta)

# Get PTID for mri meta
#submridx <- merge(submrimeta, dxsum_ptid, by.x=c("RID", "VISCODE"), by.y=c("RID", "VISCODE"))

# Get VISCODE for dbcsv
sbjid <- data.frame(do.call('rbind', strsplit(as.character(dbcsv$Subject),'_S_',fixed=TRUE)))
dbcsv$siteid = as.integer(as.character(sbjid$X1))
dbcsv$RID = as.integer(as.character(sbjid$X2))
dbcsv$Acq.Date = as.Date(dbcsv$Acq.Date, "%m/%d/%Y")
dbcsv = merge(submrimeta, dbcsv,by.x=c("RID", "EXAMDATE"), by.y=c("RID", "Acq.Date"))
dbcsv <- merge(dbcsv, sub_dxsum, by.x=c("RID", "VISCODE"), by.y=c("RID", "VISCODE"), all.x=TRUE)

dbcsv$DXCHANGE = replacebyneighbour(dbcsv$DXCHANGE)

print(sprintf("dbgen.csv was generated in: %s", dbpath))
