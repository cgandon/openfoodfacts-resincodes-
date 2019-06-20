#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun  7 10:41:11 2019

@author: macbook
"""

import requests as r
import pandas as pd
import os as os
import json as json
import cv2
from sklearn.cluster import KMeans
from sklearn.cluster import KMeans
from sklearn.cluster import DBSCAN  
import seaborn as sns
from fuzzywuzzy import process
from fuzzywuzzy import fuzz
import numpy as np


# =============================================================================
# STEP 1 - FUNCTION DEFINITIONS
# =============================================================================

def ocr_json_load(file): # open the JSON file produced by Google Cloud Vision OCR API 
    with open(file) as json_file:  
        return json.load(json_file)["textAnnotations"]

def show_ocr_source_image(image): # show the source image up on screen
    img = cv2.imread(image,1)
    height, width, depth = img.shape
    img2 = cv2.resize(img,(int(height/10), int(width/10)))
    cv2.imshow('image',img2)
    cv2.waitKey(-1)
    cv2.destroyWindow('image')

def ocr_json_extract(data): # extract content from OCR file with texts and bounding box coordinates
    content = pd.DataFrame(index = range(len(data)), columns=["text","kmeans_3","dbscan","x0","x1","x2","x3","y0","y1","y2","y3"])
    n = 0
    for items in data:
        content.loc[n,"text"]=items["description"]    
        content.loc[n,"x0"]=items["boundingPoly"]["vertices"][0]["x"]
        content.loc[n,"x1"]=items["boundingPoly"]["vertices"][1]["x"]
        content.loc[n,"x2"]=items["boundingPoly"]["vertices"][2]["x"]
        content.loc[n,"x3"]=items["boundingPoly"]["vertices"][3]["x"]
        content.loc[n,"y0"]=items["boundingPoly"]["vertices"][0]["y"]
        content.loc[n,"y1"]=items["boundingPoly"]["vertices"][1]["y"]
        content.loc[n,"y2"]=items["boundingPoly"]["vertices"][2]["y"]
        content.loc[n,"y3"]=items["boundingPoly"]["vertices"][3]["y"]
        n+=1
#    sorted = content.sort_values("y3", ascending=False).sort_values("x0", ascending=True) # sort ascending by upper left point Y coordinates, then lower left point X coordinates
    return content

def find_nb_columns(content,columns = None):
# build columns (assumed 3 for now)
    kmeans_i = []
    kmeans_score = []
    for i in range(1,10):        
        kmeans_i.append(i)
        kmeans_tmp = KMeans(n_clusters = i, 
                    init="k-means++", 
                    max_iter = 400, 
                    n_init = 10,
                    random_state = 0)    
        result_tmp = kmeans_tmp.fit(content.loc[:,"x0"].values.reshape(-1,1))        
        kmeans_score.append(kmeans_tmp.inertia_)
    kmeans_result = pd.DataFrame()
    kmeans_result["i"] = kmeans_i
    kmeans_result["score"] = kmeans_score
        
    
    for i in kmeans_result["i"]:
        try:
            kmeans_result.loc[i,"elbow"] = (kmeans_result.loc[i,"score"]-kmeans_result.loc[i-1,"score"])/(kmeans_result.loc[i+1,"score"]-kmeans_result.loc[i,"score"])
        except:
            pass
    sns.lineplot(x=kmeans_i,y=kmeans_score)
    if columns is None:
        best = kmeans_result.i[kmeans_result["elbow"] == kmeans_result["elbow"].max()].values[0]
        print("Best match identified: {} columns".format(best))
    else:
       best = columns
       print("forced to {} columns".format(best))
    kmeans_tmp = KMeans(n_clusters = best, 
            init="k-means++", 
            max_iter = 400, 
            n_init = 10,
            random_state = 0)    
    result_tmp = kmeans_tmp.fit(content.loc[:,"x0"].values.reshape(-1,1))        
    return kmeans_tmp

def build_nutriment_table(content, kmeans_tmp): # map text into back into a table format     

    content["kmeans_3"] = kmeans_tmp.labels_
        
    # build lines (better use DBSCAN when you cannot tell how many centroids in advance)
    dbscan = DBSCAN(algorithm='auto', eps=50, metric='euclidean', metric_params=None, min_samples=1, n_jobs=None, p=None).fit(content.loc[:,"y0"].values.reshape(-1,1))
    dbscan.labels_
    content["dbscan"] = dbscan.labels_
    
    # consolidate results in table
    table = pd.DataFrame(dtype = str, columns= content.kmeans_3.value_counts().index.values, index = content.dbscan.value_counts().index.sort_values().values)    
    for x in content["dbscan"].value_counts().index.values:
        for y in content["kmeans_3"].value_counts().index.values:
            table.loc[x,y] = content.loc[(content["kmeans_3"]==y) & (content["dbscan"]==x),"text"].str.cat(sep=" ")
    return table

def clean_nutriment_table(nut_table_raw):# identify nutriment columns   
    nut_list = ["ENERGIE","PROTEINES","GLUCIDES","LIPIDES","SUCRES","ACIDES GRAS SATURES", "FIBRES ALIMENTAIRES", "SODIUM","SELS MINERAUX", "VITAMINES"]
    nut_meas =["G","KG"]
    nut_table_clean = pd.DataFrame(index=nut_list, columns = ["label found","score_label", "quantity","score_quant"])
    for i in nut_table_clean.index:
        max_label_score = 0
        max_x = 0
        max_y = 0
        new_label_score  = 0
        new_qt_score = 0
        max_qt_score = 0
        qt_col = np.nan
        for x in nut_table_raw.index:
            for y in nut_table_raw.columns:
                new_label_score = fuzz.token_sort_ratio(nut_table_raw.loc[x,y],i)  # spot best matching label
                if new_label_score > max_label_score:
                    max_label_score = new_label_score
                    max_x = x
                    max_y = y                
        for y in nut_table_raw.columns:
            new_qt_score = sum([a.upper() in nut_meas or a.isdigit() for a in nut_table_raw.loc[max_x,y]]) # spot best matching quantities    
            if new_qt_score > max_qt_score:
                max_qt_score = new_qt_score
                qt_col = y     
        try:
            nut_table_clean.loc[i,"label found"] = nut_table_raw.loc[max_x,max_y]            
            nut_table_clean.loc[i,"score_label"] = max_label_score
            nut_table_clean.loc[i,"quantity"] = nut_table_raw.loc[max_x,qt_col]
            nut_table_clean.loc[i,"score_quant"] = max_qt_score
        except:
            pass
    return nut_table_clean

'''
#    nut_list = ["ENERGIE","ÉNERGIE","PROTEINES","PROTÉINES","GLUCIDES","LIPIDES","SUCRES","ACIDES","GRAS", "SATURES", "SATURÉS", "FIBRES", "ALIMENTAIRES", "SODIUM","SEL", "SELS", "MINERAUX", "MINÉRAUX", "VITAMINES"]
    nut_list = ["ENERGIE","PROTEINES","GLUCIDES","LIPIDES","SUCRES","ACIDES GRAS SATURES", "FIBRES ALIMENTAIRES", "SODIUM","SELS MINERAUX", "VITAMINES"]
    nut_meas =["G","KG"]
    spot_labels = nut_table_raw.copy()
    spot_qt = pd.DataFrame(index=nut_list, columns = ["label found", "quantity"])
    for i in nut_table_raw.columns:
        for j in nut_table_raw.index:
            spot_labels.loc[j,i] = sum([fuzz.token_set_ratio('Deluxe Room, 1 King Bed', 'Deluxe King Room') for r in nut_table_raw.loc[j,i].upper().split()]) 
            spot_qt.loc[j,i] = sum([(r not in nut_meas and type(r) != int) for r in nut_table_raw.loc[j,i].upper()])
    score_labels = []
    score_qt = []
    for col in spot_labels:
        score_labels.append(spot_labels[col].sum())
    for col in spot_qt:
        score_qt.append(spot_qt[col].sum())
    col_label = score_labels.index(max(score_labels))
    col_qt = score_qt.index(min(score_qt))
    
           
'''
#       spot best columns for qties
        

# identify nutriment quantities
    
    
    
==============================================================
# STEP 2 - RUN FUNCTIONS
# =============================================================================

data = ocr_json_load('test.json')
show_ocr_source_image('ex.jpg')
content = ocr_json_extract(data)
kmeans_tmp = find_nb_columns(content,3)
nut_table_raw = build_nutriment_table(content, kmeans_tmp)
nut_table_clean = clean_nutriment_table(nut_table_raw)
  


        
        
