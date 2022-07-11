# coding=utf-8
import datetime as dt
import arcpy
import arcgisscripting
import time
import math
from datetime import datetime

count_getMidPoint = 0
count_str2datetime = 0
count_gpsDataDict = 0
count_route_solver = 0
count_near_segments = 0
count_acceptSnapPoints = 0
count_clean = 0
count_solverForIAndJ = 0
count_mapMatch = 0
count_compareFID = 0

'''
getMidPoint : computation of the mid point from gps data.
parameters: None
return:
    - x_mid : mid point x coordinate .
    - y_mid : mid point y coordinate .
'''
def getMidPoint(gpsDict):
    inicio=datetime.now()
    global count_getMidPoint
    count_getMidPoint += 1
    sum_x,sum_y = 0.,0.
    for dictPoint in gpsDict.values():
        sum_x += dictPoint["gpsPoint"][0]
        sum_y += dictPoint["gpsPoint"][1]
    n = len(gpsDict)
    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( getMidPoint ): " + str( tiempo_ejecucion ) )
    return sum_x/n,sum_y/n

'''
utc2datetime : conversion from utcdate and utctime to datetime
parameters:
    - utcdate: a date (y,m,d) in datetime format.
    - strTime: a time (h,m,s) in string.
return:
    - a cambination of date and time in datetime format.

def str2datetime(strTime):
    global count_str2datetime
    count_str2datetime += 1
    #print(strTime)
    #type_time = strTime[-2:]
    #strTime = strTime[11:-3]
    #print(strTime)
    h,m,s = map(int,strTime.split(':'))
    #if type_time == 'PM': h += 12
    return datetime.datetime(1,1,1,h,m,s)


gpsDataDict: generate a dictionary from geo processing data.
parameters: None
return: None
'''
def gpsDataDict(gpsData):
    inicio=datetime.now()
    global count_gpsDataDict
    count_gpsDataDict += 1
    gpsDict = {}
    #change speed or dspeed if the set needs it
    #TODO:with arcpy.da.SearchCursor(gpsData,["OBJECTID","NEAR_X","NEAR_Y","Hora","Speed","NEAR_FID"]) as gpsCursor: #ObjectId = FID
    with arcpy.da.SearchCursor(gpsData,[ "OBJECTID","longitud","latitud","hora","velocidad","NEAR_FID", "direccion" ]) as gpsCursor: #ObjectId = FID
        for gpsRow in gpsCursor:
            h,m,s = map(int,gpsRow[3].split(':'))
            #vel = gpsRow[4].split() #TODO: velocidad viene solo el numero
            gpsDict[gpsRow[0]] = { "gpsPoint" : ( gpsRow[1], gpsRow[2] ), "time" : dt.datetime(1,1,1,h,m,s),
                                  "dSpeed" : float( gpsRow[4] ), "near_fid" : gpsRow[5], "dir" : gpsRow[6] }
        #print( "Debug: {} - gpsDict={}".format( len(gpsDict), gpsDict[14] ) )
    del gpsCursor
    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( gpsDataDict ): " + str( tiempo_ejecucion ) )
    return gpsDict

'''
route_solver : computing the route between two points.
parameters :
    - gpsDict : gps points dictionary.
    - snap_i  : current k_i point.
    - snap_j  : current k_j point.
    - i       : point index.
    - j       : point index.
return :
    - distance between snap points.
    - speed between snap points.
    - average speed between gps points.
'''
def route_solver(snap_i,snap_j,i,j,snapData,networkDataSet,currentRoute,currentRouteSearch,gpsDict,gp):
    inicio=datetime.now()
    global count_route_solver
    count_route_solver += 1
    upCursor = arcpy.da.UpdateCursor( snapData,"SHAPE@XY" )
    ## current snap point k_i
    row = upCursor.next()
    row[0] = (snap_i[0],snap_i[1])
    upCursor.updateRow(row)
    ## current snap point k_j
    row = upCursor.next()
    row[0] = (snap_j[0],snap_j[1])
    upCursor.updateRow(row)
    del upCursor

    ## generating route k_i --> k_j
    routeLayer = gp.MakeRouteLayer_na(networkDataSet, currentRoute, "LENGTH").getOutput(0)
    #gp.AddLocations_na(routeLayer, "Stops", snapData)
    gp.AddLocations_na(routeLayer, "Stops", snapData)
    ## solving route k_i --> k_j.
    gp.Solve_na(routeLayer)
    ## distance k_i --> k_j
    cursor = arcpy.da.SearchCursor(currentRouteSearch,["Total_Length"])
    row = cursor.next()
    distance = round(row[0],3)/1000. ## meters to km
    ## utcdate + utctime for k_i and k_j. 
    time_i = gpsDict[i]["time"]
    time_j = gpsDict[j]["time"]
    ## k_i and k_j speed.
    speed_i = gpsDict[i]["dSpeed"]
    speed_j = gpsDict[j]["dSpeed"]

    ## delta time k_i --> k_j.
    deltaTime = time_j - time_i
    ## travel speed k_i --> k_j.
    dt = deltaTime.total_seconds()
    #print( "distance: " + str( distance ) )#+ " time: "+str(deltaTime.total_seconds() )
    if(dt==0):
         dt=1 
    
    speedSnap = round(3600*distance/dt,3) ## km/sec is converted to km/hr
    ## average speed.
    #print(speed_i, speed_j)
    averageSpeed = round( .5 * (speed_i + speed_j) , 3)

    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( route_solver ): " + str( tiempo_ejecucion ) )
    return distance,speedSnap,averageSpeed

'''
near_segments : search all segments which are inside of a determined radius.
parameters:
    - i           : point index.
    - snapDict    : dictionary of snap points.
    - gpsDict     : gps points dictionary.
return:
    - snapDict modified, where the near segments and corresponding snap
    points for the gps point i has been added.
'''
def near_segments(index,tempData,roadway,tempTable,searchRadius,gpsDict,snapDict):
    inicio=datetime.now()
    global count_near_segments
    count_near_segments += 1
    nearList = []

    # angle tolerance range parameter (t_angle/2)
    t_angle = 5 # tollerance: 10

    upCursor = arcpy.da.UpdateCursor(tempData,"SHAPE@XY")
    #print( "Debug: upCursor = {}".format(upCursor) )
    #print( GetGeographicalDegrees() )
    row = upCursor.next()
    #print( "Debug: row={}".format(row) )
    #print( "Debug: gpsPoints={}{}".format( gpsDict[index]["gpsPoint"][0], gpsDict[index]["gpsPoint"][1] ) )

    row[0] = ( gpsDict[index]["gpsPoint"][0], gpsDict[index]["gpsPoint"][1] )
    upCursor.updateRow(row)
    del upCursor
    
    arcpy.GenerateNearTable_analysis(tempData,roadway,tempTable,searchRadius,"LOCATION","ANGLE","ALL","","GEODESIC")
    #arcpy.GenerateNearTable_analysis(tempData,roadway,tempTable,searchRadius,"LOCATION","ANGLE","ALL","","GEODESIC")
    #"LOCATION","ANGLE","ALL","","GEODESIC")
    auxRow = []
    flag = True
    with arcpy.da.SearchCursor(tempTable,["NEAR_DIST","NEAR_FID","NEAR_X","NEAR_Y", "NEAR_ANGLE"]) as tempCursor:
        for row in tempCursor:
            #FP: filtrar calles que tengan la misma direccion 
            angle = angle1 = angle2 = int(row[4])
            if(flag):
                auxRow = row
                flag = False
            
            if ( angle < 0 and angle > -180): 
                angle = angle + 360
            
            if( angle < 90 ):
                angle1 = angle + 90
                angle2 = angle1 + 180
            elif( angle < 270 ):
                angle1 = angle - 90
                angle2 = angle1 + 180
            else:
                angle1 = angle - 270
                angle2 = angle1 + 180

            #print( "Debug: [{}]: nearFID = [{};{}] angleNear = [{};{}] - dir = {} - angleRoad = [{};{}]".format( index, row[1], gpsDict[index]["near_fid"], int(row[4]), angle, gpsDict[index]["dir"], angle1, angle2 ) )
            #print( "Debug: [{}]: dir = {} - angleRoad = [{};{}]".format( index, gpsDict[index]["dir"], angle1, angle2 ) )
            print( "Debug: " + str(index == 1 or index == len(gpsDict)) )
            if(index == 1 or index == len(gpsDict)):
                nearList.append(row)
                print("Debug: index = 1 - " + str(len(gpsDict)))
                continue #Add only one near
            elif( ( angle1 - t_angle<  gpsDict[index]["dir"] < angle1 + t_angle) or ( angle2 - t_angle<  gpsDict[index]["dir"] < angle2 + t_angle) ):
                nearList.append(row)
    
    if( len(nearList) == 0 ):
        nearList.append(auxRow)

    #print("")
    print( "Debug: nearList={}".format(nearList) )

    #nearList.sort() #TODO: validado, no hace nada
    ## print "id:{} -- point:{} -- nearList:{}".format(index,gpsDict[index]["gpsPoint"],nearList)
    del tempCursor
    
    #if nearList == []:
    #    nearList = near_segments(index,tempData,roadway,tempTable,searchRadius+1,gpsDict,snapDict)
    #else:
    #    snapDict[index] = nearList
    #    return snapDict

    snapDict[index] = nearList
    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( near_segments ): " + str( tiempo_ejecucion ) )
    return snapDict

'''
acceptSnapPoints : generate a feature class with the accepted snap points.
parameters:
    - acceptDict: dictionary with the accepted snap points.
return: None
'''
def acceptSnapPoints(n,finalData,acceptDict,spatial_reference):
    inicio=datetime.now()
    global count_acceptSnapPoints
    count_acceptSnapPoints += 1
    #arcpy.CreateFeatureclass_management(arcpy.env.workspace, finalData, "POINT", "", "DISABLED", "DISABLED", spatial_reference)
    finalCursor = arcpy.da.InsertCursor(finalData,["SHAPE@XY"])
    i = 1
    while i <= n:
        finalCursor.insertRow([acceptDict[i][0]])
        i += 1
    del finalCursor
    
    arcpy.AddField_management(finalData, "FID", "LONG")
    i = 1
    with arcpy.da.UpdateCursor(finalData,["FID"]) as finalCursor:
        for finalRow in finalCursor:
            finalRow[0] = acceptDict[i][1]
            finalCursor.updateRow(finalRow)
            i += 1
    del finalCursor
    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( acceptSnapPoints ): " + str( tiempo_ejecucion ) )

'''
clean : clean the feature classes used.
parameters: None
return: None
'''
def clean(snapData,tempData,assignData,tempTable,assignTable):
    inicio=datetime.now()
    global count_clean
    count_clean += 1
    if arcpy.Exists(snapData):
        arcpy.Delete_management(snapData)
    if arcpy.Exists(tempData):
        arcpy.Delete_management(tempData)
    if arcpy.Exists(tempTable):
        arcpy.Delete_management(tempTable)
    if arcpy.Exists(assignData):
        arcpy.Delete_management(assignData)
    if arcpy.Exists(assignTable):
        arcpy.Delete_management(assignTable)

    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( clean ): " + str( tiempo_ejecucion ) )
'''
mapMatch : 
parameters:
    - j: id number of point.
return: None
'''

def solverForIAndJ(i,j,pointsToCheck,snapDict,acceptDict,tol_rs,snapData,networkDataSet,currentRoute,currentRouteSearch,gpsDict,gp,tempData,roadway,tempTable,searchRadius,n):
    inicio=datetime.now()
    global count_solverForIAndJ
    count_solverForIAndJ += 1
    
    forward = False

    print( "Input i: " + str(i) + " FID: " + str(gpsDict[i]["near_fid"]) )
    print( "Input j: " + str(j) + " FID: " + str(gpsDict[j]["near_fid"]) )

    fid_i = acceptDict[i][1] 
    snap_i = acceptDict[i][0] 

    if(j >= n):
        j = n
    try:
        while pointsToCheck > 0:
            if(len(snapDict[j]) > 0):
                # Revisar i -> street[j]
                if i < 1: #In case of being close to 1, without this if the program brakes because of boundries.
                        print( "no more i for iterations" )# going for j now
                        break 
                fid_i = acceptDict[i][1] 
                snap_i = acceptDict[i][0] 
                if fid_i > 0 and len(snapDict[j])>0:
                        #print "entro el j alt"
                    print( "Searching for alt j (" + str(j) + ")" )
                    print("Started_FID_i: ",fid_i)
                    #print("Debug: " + str(len(snapDict[j])))
                    for street in snapDict[j]:
                        fid_j = street[1]
                        snap_j = (street[2],street[3])
                        dist,snapSpeed,avSpeed = route_solver(snap_i,snap_j,i,j,snapData,networkDataSet,currentRoute,currentRouteSearch,gpsDict,gp)
                    
                        if snapSpeed - tol_rs <= avSpeed <= snapSpeed + tol_rs:   
                            print( "solution found!" )
                            print( "i: " +str(i)+ "  &   j: " +str(j) )
                            print( "iFID: " +str(fid_i)+ "  &   jFID: " +str(fid_j) )
                            print( dist )
                            fin=datetime.now()
                            tiempo_ejecucion=fin-inicio
                            print( "Time function( solverForIAndJ ): " + str( tiempo_ejecucion ) )
                            return True, (snap_i, fid_i), (snap_j, fid_j), i, j

                # Revisar street[i] -> j
                if( i > 1):
                    snap_im = acceptDict[i-1][0]
                    fid_j = snapDict[j][0][1]
                    snap_j = (snapDict[j][0][2],snapDict[j][0][3])
                    set_FID_i = {fid_i}
                    print( "Searching for alt i (" + str(i) + ")" )
                    print("Started_FID_j: ",fid_j)
                    for street in snapDict[i]: #<------------------ Falla
                        fid_i = street[1]
                        if(fid_i not in set_FID_i):
                            snap_i = (street[2],street[3])
                            dist_A,snapSpeed_A,avSpeed_A = route_solver(snap_im,snap_i,i - 1,i,snapData,networkDataSet,currentRoute,currentRouteSearch,gpsDict,gp)
                            dist_B,snapSpeed_B,avSpeed_B = route_solver(snap_i,snap_j,i,j,snapData,networkDataSet,currentRoute,currentRouteSearch,gpsDict,gp)
                            if (snapSpeed_A - tol_rs <= avSpeed_A <= snapSpeed_A + tol_rs) and (snapSpeed_B - tol_rs <= avSpeed_B <= snapSpeed_B + tol_rs):
                                print( "solution found!" )
                                print( "i: " +str(i)+ "  &   j: " +str(j) )
                                print( "iFID: " +str(fid_i)+ "  &   jFID: " +str(fid_j) )
                                fin=datetime.now()
                                tiempo_ejecucion=fin-inicio
                                print( "Time function( solverForIAndJ ): " + str( tiempo_ejecucion ) )
                                return True, (snap_i, fid_i), (snap_j,fid_j), i, j

                if(not(forward)):
                    i -= 1
                    pointsToCheck -= 1          
                    if i < 1: #In case of being close to 1, without this if the program brakes because of boundries.
                        print( "no more i for iterations" )# going for j now
                        break
                    forward = True
                else:      
                    j += 1
                    if j >= n:
                        print( "no more j for itereation, final point" )
                        fin=datetime.now()
                        tiempo_ejecucion=fin-inicio
                        print( "Time function( solverForIAndJ ): " + str( tiempo_ejecucion ) )
                        return False, (snap_i, fid_i), (gpsDict[n]['gpsPoint'],0), i, n
                    pointsToCheck -= 1
                    if j not in snapDict:
                        snapDict = near_segments(j,tempData,roadway,tempTable,searchRadius,gpsDict,snapDict)
                    forward = False

            else:    
                movinPos = "j"
                j += 1
                if j >= n:
                    print( "no more j for itereation, final point" )
                    fin=datetime.now()
                    tiempo_ejecucion=fin-inicio
                    print( "Time function( solverForIAndJ ): " + str( tiempo_ejecucion ) )
                    return False, (snap_i, fid_i), (gpsDict[n]['gpsPoint'],0), i, n
                pointsToCheck -= 1
                if j not in snapDict:
                    snapDict = near_segments(j,tempData,roadway,tempTable,searchRadius,gpsDict,snapDict)
                forward = False

        print( "didn't find matching i or j" )
        fin=datetime.now()
        tiempo_ejecucion=fin-inicio
        print( "Time function( solverForIAndJ ): " + str( tiempo_ejecucion ) )
        return False, (snap_i, fid_i), (gpsDict[n]['gpsPoint'],0), i, j
        
    except arcpy.ExecuteError:
        err=str(j)+": "+arcpy.GetMessages(2)
        print (arcpy.GetMessages(2))
        fin=datetime.now()
        tiempo_ejecucion=fin-inicio
        print( "Time function( solverForIAndJ ): " + str( tiempo_ejecucion ) )
        return False, (snap_i, fid_i), (gpsDict[n]['gpsPoint'],0), i, j                 




def mapMatch(i,j,tol_rs,snapData,tempData,assignData,tempTable,assignTable,searchRadius,currentRoute,currentRouteSearch,networkDataSet,roadway,gpsDict,snapDict,acceptDict,gp,n_points,n):
    inicio=datetime.now()
    global count_mapMatch
    count_mapMatch += 1
    ## searching near segments for gps_j
    try:
        it = i

        realI = i
        realJ = j
        
        if j not in snapDict:
            snapDict = near_segments(j,tempData,roadway,tempTable,searchRadius,gpsDict,snapDict)
        
        # Here starts the routing   
        pointsToCheck = n_points
        print( "PointsToCheck: "+str(pointsToCheck) )

        solution, resultado_i, resultado_j, i, j = solverForIAndJ(i,j,pointsToCheck,snapDict,acceptDict,tol_rs,snapData,networkDataSet,currentRoute,currentRouteSearch,gpsDict,gp,tempData,roadway,tempTable,searchRadius,n)

        if( j == n and resultado_j[1] == 0 ):
            acceptDict[n] = resultado_j
        if solution:
            acceptDict[j] = resultado_j
            acceptDict[i] = resultado_i
            if j - i > 1:
                print( "Routing..." )
                assignList = []
                arcpy.MakeFeatureLayer_management(currentRouteSearch, "routeIn")
                arcpy.MakeFeatureLayer_management(roadway, "roadway")
                arcpy.SelectLayerByLocation_management("roadway", 'SHARE_A_LINE_SEGMENT_WITH', "routeIn")
                #arcpy.SelectLayerByLocation_management("roadway", 'SHARE_A_LINE_SEGMENT_WITH', "routeIn")   REVISAR
                
                for row in arcpy.da.SearchCursor("roadway",["OBJECTID"]):
                    assignList.append(row[0])
                
                
                print( "{}-->{} - Assign List:{}".format(i,j,assignList) )
                
                for oid in range( i + 1, j ):
                    #print "i:{} - j:{}".format(i,j)
                    print( "Forcing points between " + str(i) + " and " + str(j) )
                    ## if the point is already in the snap dictionary,  
                    ## the closer point is assigned.
                    #oidIsAssign = False
                    '''
                    if oid in snapDict:

                        
                        print "{} - near: {}".format(oid,snapDict[oid])
                        if len(snapDict[oid]) > 0:
                            fid_oid = snapDict[oid][0][1]
                        else:
                            fid_oid = 0
                        if fid_oid in assignList:
                            snap_oid = (snapDict[oid][0][2],snapDict[oid][0][3])
                            acceptDict[oid] = (snap_oid,fid_oid)
                            oidIsAssign = True
                        else:
                            oidIsAssign = False
                                
                    ## if the point is not in the snap dictionary,
                    ## from the fid in the route, the closer one is assigned.
                    '''
                    #if not oidIsAssign:
                    
                    upCursor = arcpy.da.UpdateCursor(assignData,"SHAPE@XY")
                    row = upCursor.next()
                    print( oid )
                    row[0] = ( gpsDict[oid]["gpsPoint"][0],gpsDict[oid]["gpsPoint"][1] )
                    
                    upCursor.updateRow(row)
                    del upCursor
                    
                    arcpy.GenerateNearTable_analysis(assignData,roadway,assignTable,"","LOCATION","NO_ANGLE","CLOSEST")# aqui busco la calle mas cercana
                    with arcpy.da.SearchCursor(assignTable,["NEAR_DIST","NEAR_FID","NEAR_X","NEAR_Y"]) as assignCursor:
                        row = assignCursor.next()
                        print( row )
                        acceptDict[oid] = ( (row[2], row[3] ), row[1] ) 
                    print( "assign: ",acceptDict[oid] )
                arcpy.SelectLayerByAttribute_management("roadway", "CLEAR_SELECTION")
        fin=datetime.now()
        tiempo_ejecucion=fin-inicio
        print( "Time function( mapMatch ): " + str( tiempo_ejecucion ) )
        return acceptDict, realI, realJ, solution
    except arcpy.ExecuteError:
        err = str(j) + ": " + arcpy.GetMessages(2)
        print( err + " :: " + arcpy.GetMessages(2) )
        fin=datetime.now()
        tiempo_ejecucion=fin-inicio
        print( "Time function( mapMatch ): " + str( tiempo_ejecucion ) )
        pass

def compareFID(n,finalData,gpsDict):
    inicio=datetime.now()
    global count_compareFID
    count_compareFID += 1
    mmList = []
    badList=[]
    realList = []
    
    #FID: MapMatching value result
    with arcpy.da.SearchCursor(finalData,["FID"]) as finalCursor:
        for finalRow in finalCursor:
            mmList.append(finalRow[0])
    del finalCursor
    #print (mmList)
    
    for i in range( 1, n+1 ):
        realList.append( gpsDict[i]["near_fid"] )

    matchList = []
    # i for i,j in zip(mmList,realList) if i == j
    x = 1
    for i,j in zip( mmList,realList ):
        if(i==j):
            matchList.append( (x, i, j) )
        else:
            badList.append( (x, i, j) )
        x += 1
    print( "Points with not solution: ", badList )
    countAnalysis()
    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( compareFID ): " + str( tiempo_ejecucion ) )
    return ( matchList )

def countAnalysis():
    inicio=datetime.now()
    global count_getMidPoint, count_str2datetime, count_gpsDataDict, count_route_solver
    global count_near_segments, count_acceptSnapPoints, count_clean
    global count_solverForIAndJ, count_mapMatch, count_compareFID

    print( "count_getMidPoint = {}".format( count_getMidPoint ) )
    print( "count_str2datetime = {}".format( count_str2datetime ) )
    print( "count_gpsDataDict = {}".format( count_gpsDataDict ) )
    print( "count_route_solver = {}".format( count_route_solver ) )
    print( "count_near_segments = {}".format( count_near_segments ) )
    print( "count_acceptSnapPoints = {}".format( count_acceptSnapPoints ) )
    print( "count_clean = {}".format( count_clean ) )
    print( "count_solverForIAndJ = {}".format( count_solverForIAndJ ) )
    print( "count_mapMatch = {}".format( count_mapMatch ) )
    print( "count_compareFID = {}".format( count_compareFID ) )

    count_getMidPoint = 0
    count_str2datetime = 0
    count_gpsDataDict = 0
    count_route_solver = 0
    count_near_segments = 0
    count_acceptSnapPoints = 0
    count_clean = 0
    count_solverForIAndJ = 0
    count_mapMatch = 0
    count_compareFID = 0
    fin=datetime.now()
    tiempo_ejecucion=fin-inicio
    print( "Time function( countAnalysis ): " + str( tiempo_ejecucion ) )