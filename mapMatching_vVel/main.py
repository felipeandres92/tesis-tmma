from functions import *
import os
import sys

arcpy.env.overwriteOutput = True        
arcpy.env.workspace = u'C:\\Users\\felip\\Documents\\ArcGIS\\Default.gdb'

roadway = r"RencaRedVial\RedVialComunasSantiago"
networkDataSet = r"RencaRedVial\RencaRedVial_ND"

## feature class data
#Name of the serie that you will map-match
serie_name="T"#recordar incluir el _

snapData = "snapData"
tempData = "tempData"
assignData = "assignData"
tempTable = "tempTable"
currentRoute = "currentRoute"
currentRouteSearch = "currentRoute/Routes"
assignTable = "assignTable"

## dictionary with the results
d_res = {}
## dictionary with amount of gps points.
d_gps = {}
## speed tolerance range parameter (rs/2) (km/hr).
tol_rs_List = [8] # tolerance 16
## buffer parameter
searchRadius_List = [4] #temp value, SearchRadio update value

## sampling frequency (temporal resolution)
samp_freq_List = [10]

## amount of points
n_points = 5

#Listing all the datasets in the geodatabase
featureclasses = arcpy.ListFeatureClasses()

print( datetime.now() )

#Select the datasets that start with name of the serie
datasets=[]
for featureclass in featureclasses:
    #if( featureclass.startswith("T386_20150212_1389_1466") or featureclass.startswith("T916_20150208_2161_2196") ):
    if( featureclass.startswith(serie_name) ):
        datasets.append(featureclass)

spatial_reference = arcpy.Describe(datasets[0]).spatialReference
arcpy.management.CreateFeatureDataset(arcpy.env.workspace,serie_name+"_results",spatial_reference)
print(datasets) #FP: List datasets selected

print("The map matching algorithm is running now, this could take a few minutes ...")
original_stdout = sys.stdout # Save a reference to the original standard output

for dataset in datasets:
    fc_data_fp = fc_data = dataset

    # FP: SearchRadio
    arcpy.MakeFeatureLayer_management( fc_data_fp, "dataset" )
    nPointsData = float( arcpy.GetCount_management( "dataset" ).getOutput(0) )
    #print( "{} - Puntos GPS: {}".format( nPointsData, fc_data_fp) )
    
    r = cont = base = 2
    cobertura = 0.0
    while cobertura <= 99:
        searchRadius_List[0] = r
        nPointsSelected = float( arcpy.GetCount_management( arcpy.SelectLayerByLocation_management("dataset", 'WITHIN_A_DISTANCE', 'RedVialComunasSantiago', str(r)+' Meters', 'NEW_SELECTION','NOT_INVERT')  ).getOutput(0) )
        cobertura = ( nPointsSelected / nPointsData * 100 )
        #print ( "Radio: {} Metros: {} puntos seleccionados - {}%".format(r, nPointsSelected, round(cobertura) ) ) #porcentaje del total
        r = base**cont
        cont += 1
        if r > 600:
            cobertura = 100
    arcpy.SelectLayerByAttribute_management("dataset", "CLEAR_SELECTION")
    # FP: End SearchRadio

    #           T386_20150207_2302_2341_t4_r16_logs.txt*
    filename = fc_data + '_t' + str(tol_rs_List[0]) + '_r' + str(searchRadius_List[0]) + '_logs.txt'
    with open(filename, 'w') as f:
        sys.stdout = f # redirect the output to the log text file
        
        for samp_freq in samp_freq_List:
            ## Create the geoprocessor object.
            gp = arcgisscripting.create(9.3)  # allow backward compatibility down to ArcGIS 9.3
            ## Set the necessary product code.
            gp.SetProduct("ArcInfo")
            ## Check out any necessary licenses.
            gp.CheckOutExtension("Network")
            serie_List = range( 1,samp_freq/10 + 1)
            
            print( "Serie: ", serie_List )#TODO: probando que contiene
            
            for serie in serie_List:
                gpsData = fc_data#"data_" + str(fc_data) + "_" + str(samp_freq) + "sec_" + str(serie)
                print(gpsData)
                ## dictionary with the gps points --> {objectID: "gpsPoint":(x,y),"time":str,"dSpeed":float}
                gpsDict = gpsDataDict( gpsData )
                #print( gpsDict ) #TODO: prueba
                
                for tol_rs in tol_rs_List:
                    for sr in searchRadius_List:
                        searchRadius = str(sr) + " Meters" #Changed from Feets to Meters, searchRadius should use meters now
                        finalData = "Final_"+fc_data+ '_' + str(tol_rs) + '_' + str(sr) 

                        start = time.clock()
                        inicio=datetime.now()
                        ## dictionary with near segments and corresponding snap points.
                        snapDict = {}
                        ## dictionary with the accepted snap points.
                        acceptDict = {}

                        ## the spatial reference from gpsData is obtained.
                        spatial_reference = arcpy.Describe(gpsData).spatialReference

                        
                        if samp_freq not in d_gps:
                            d_gps[samp_freq] = {}
                        if serie not in d_gps[samp_freq]:
                            
                            d_gps[samp_freq][serie] = len(gpsDict)

                        print ("gps dictionary done...")

                        x_mid,y_mid = getMidPoint(gpsDict)
                        print ("midPoint : ({},{})".format(x_mid,y_mid))

                        ## a temporal feature class for a gps point.
                        arcpy.CreateFeatureclass_management(arcpy.env.workspace, tempData, "POINT", "", "DISABLED", "DISABLED", spatial_reference)
                        tempCursor = arcpy.da.InsertCursor(tempData,["SHAPE@XY"])
                        tempCursor.insertRow([(x_mid,y_mid)])
                        del tempCursor

                        ## feature class for snap_i and snap_j.
                        arcpy.CreateFeatureclass_management(arcpy.env.workspace, snapData, "POINT", "", "DISABLED", "DISABLED", spatial_reference)
                        snapCursor = arcpy.da.InsertCursor(snapData,["SHAPE@XY"])
                        snapCursor.insertRow([(x_mid,y_mid)])
                        snapCursor.insertRow([(x_mid,y_mid)])
                        del snapCursor

                        ## a temporal feature class for snap assignment.
                        arcpy.CreateFeatureclass_management(arcpy.env.workspace, assignData, "POINT", "", "DISABLED", "DISABLED", spatial_reference)
                        assignCursor = arcpy.da.InsertCursor(assignData,["SHAPE@XY"])
                        assignCursor.insertRow([(x_mid,y_mid)])
                        del assignCursor

                        n = len(gpsDict)
                        print("n: "+str(n))
                        #print ("-----------")
                        #print (acceptDict)
                        #print ("-----------")
                        #print (gpsData)
                        #print ("-----------")
                        #print (gpsDict)
                        #print ("-----------")
                        #print (gpsDict.values()[0])
                        #print ("-----------")
                        #print (gpsDict.values()[1])
                        #print ("-----------")
                        #asd = gpsDict.values()[1]
                        #print (asd.values()[2])
                        #print ("-----------")
                        #print (gpsDict[0]['gpsPoint'])
                        print ("-----------")
                        keys= gpsDict.keys()
                        values= gpsDict.values()

                        for i in range(1,n+1):
                                                #iteration = gpsDict.values()[i]
                                                #print(iteration.values[2])
                                                #tempVar = iteration.values[2]
                                                #acceptDict[i] = (tempVar,0)
                                                try:
                                                        #print("key: "+str(keys[i])+" value: "+str(values[i]))
                                                        acceptDict[i] = (gpsDict[i]['gpsPoint'],0)
                                                        
                                                except:
                                                        pass
                        ## assign first point to a route
                        snapDict = near_segments(1,tempData,roadway,tempTable,searchRadius,gpsDict,snapDict)
                        
                        if snapDict[1] == []:
                            acceptDict[1] = (gpsDict[1]['gpsPoint'],0)
                            print ("Accepted: {}({})\n".format(1,0))
                        else:
                            fid = snapDict[1][0][1]
                            snap = (snapDict[1][0][2],snapDict[1][0][3])
                            acceptDict[1] = (snap,fid)
                            print ("Accepted: {}({})\n".format(1,fid))
                        
                        j = 1
                        solution = True
                        #Feature dataset finalData
                        output_path = arcpy.env.workspace+"\\"+serie_name+"_results"
                        
                        
                        arcpy.CreateFeatureclass_management(output_path, finalData, "POINT", "", "DISABLED", "DISABLED", spatial_reference)
                        arcpy.AddField_management(finalData, "FID", "LONG")
                        print("============================ Parameters ====================================")
                        print("Sample frencuency: "+str(samp_freq)+"\n")
                        print("Points Snapped: "+str(len(gpsDict))+"\n")
                        print("Speed tolerance range: "+str(tol_rs)+"\n")
                        print("Search Radius: "+str(searchRadius)+"\n")
                        print("============================================================================")
                        while j < n:
                            print ("------------------------")
                        
                            acceptDict,i,j,solution = mapMatch( j, j+1, tol_rs, snapData, tempData, assignData,
                                                    tempTable, assignTable, searchRadius, currentRoute, currentRouteSearch,
                                                    networkDataSet, roadway, gpsDict, snapDict, acceptDict, gp, n_points, n)
                            #finalCursor = arcpy.da.InsertCursor(finalData,["SHAPE@XY"])

                            #finalCursor.insertRow([acceptDict[j-1][0]])
                            #del finalCursor
                            #finalCursor=arcpy.da.UpdateCursor(finalData,["FID"])

                            #for finalRow in finalCursor:
                                    #finalRow[0] = acceptDict[j-1][1]

                                    #finalCursor.updateRow(finalRow)
                            #del finalCursor

                        #print (acceptDict)
                        print("============================ Results ====================================")
                        acceptSnapPoints( n, finalData, acceptDict, spatial_reference ) #layer final
                        clean( snapData, tempData, assignData, tempTable, assignTable )
                        res = compareFID( n, finalData, gpsDict )

                        end = time.clock()
                        fin=datetime.now()
                        
                        time_elapsed = (end - start)/60
                        to_seconds=int(time_elapsed)+((time_elapsed-int(time_elapsed))*60)/100
                        time_elapsed=to_seconds

                        if samp_freq not in d_res:
                            d_res[samp_freq] = {}
                        if tol_rs not in d_res[samp_freq]:
                            d_res[samp_freq][tol_rs] = []
                        d_res[samp_freq][tol_rs].append((searchRadius,serie,len(res),round(time_elapsed,3)))

                        tiempo_ejecucion=fin-inicio
                        
                        print( "Time of execution(computacional): " + str( round(time_elapsed, 3) ) + "\n" )
                        print( "Time of execution(fin-inicio): " + str( tiempo_ejecucion ) )
                        print("=========================================================================")

                        sys.stdout = original_stdout # Reset the standard output to its original valu
                        print( "d_gps={}".format( d_gps ) )
                        print( "d_res={}".format( d_res ) )
                        sys.stdout = f # redirect the output to the log text file

sys.stdout = original_stdout # Reset the standard output to its original valu
