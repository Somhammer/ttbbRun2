import sys, os
import google.protobuf

os.environ["CUDA_VISIBLE_DEVICES"] = "3"

import pandas as pd
import csv
import math
import numpy as np
from array import array
from sklearn.preprocessing import StandardScaler, label_binarize
from sklearn.utils import shuffle
from operator import itemgetter
from itertools import groupby

from ROOT import *
import ROOT

import tensorflow as tf
import keras
from keras.utils import np_utils, multi_gpu_model
from keras.models import Model, Sequential, load_model
from keras.layers import Input, Dense, Activation, Dropout, add
from keras.layers.normalization import BatchNormalization
from keras.regularizers import l2
from keras.optimizers import Adam, SGD
from keras.callbacks import Callback, ModelCheckpoint

import utils as ut

def ana(inputDir, process, outputDir,flag1=False) :
    timer = ROOT.TStopwatch()
    timer.Start()

    ver = ""
    configDir = ""
    weightDir = ""
    modelfile = ""

    with open('var.txt', 'r') as f :
        while True :
            line = f.readline()
            if not line : break
            tmp = line.split()
            if 'ver' in tmp : ver = tmp[1]
            if 'configDir' in tmp : configDir = tmp[1]
            if 'weightDir' in tmp : weightDir = tmp[1]
            if 'modelfile' in tmp : modelfile = tmp[1]

    print "Load modelfile : "+str(modelfile)
    model = load_model(configDir+weightDir+ver+'/'+modelfile)
    model.summary()

    if not os.path.exists(outputDir+'/'+modelfile):
        os.makedirs(outputDir+'/'+modelfile)

    closureTest = flag1
    data = False
    ttbb = False
    if 'Data' in process : data = True
    if 'ttbb' in process : ttbb = True

    df = pd.read_hdf("array/array_train_ttbb.h5")
    nMatchable = 4864
    #ttbbFilter nMatchable: 5557
    countMatchable = True
    if countMatchable :
        df = df.filter(['signal','event','dR'], axis=1)
        df = df.query('signal > 0')
        #tmpId = df.groupby(['event'])['dR'].transform(max) == df['dR']
        #df = df[tmpId]
        df.reset_index(drop=True, inplace=True)
        nMatchable = len(df.index)
        print(nMatchable)
        f_tmp = open('matchable.txt','w')
        f_tmp.write(str(nMatchable))
        f_tmp.write(str(df))
        f_tmp.close()

    muon_ch = 0
    muon_pt = 30.0
    muon_eta = 2.1
    electron_ch = 1
    electron_pt = 35.0
    electron_eta = 2.1
    jet_pt = 30.0
    jet_eta = 2.4
    jet_CSV = 0.9535
    jet_CSV_medium = 0.8484
    number_of_jets = 6
    number_of_bjets = 2
    nChannel = 2
    nStep = 4

    if closureTest : f_out = ROOT.TFile(outputDir+'/'+modelfile+'/hist_closure.root', 'recreate')
    else : f_out = ROOT.TFile(outputDir+'/'+modelfile+'/hist_'+process+'.root', 'recreate')

    RECO_NUMBER_OF_JETS_ = "nJets"
    RECO_NUMBER_OF_BJETS_ = "nBjets"
    RECO_ADDJETS_DELTAR_ = "RecoJetDeltaR"
    RECO_ADDJETS_INVARIANT_MASS_ = "RecoJetInvMass"
    GEN_ADDBJETS_DELTAR_ = "GenbJetDeltaR"
    GEN_ADDBJETS_INVARIANT_MASS_ = "GenbJetInvMass"
    RESPONSE_MATRIX_DELTAR_ = "ResponseMatrixDeltaR"
    RESPONSE_MATRIX_INVARIANT_MASS_ = "ResponseMatrixInvMass"

    nbins_reco_addjets_dr = 12 #4
    reco_addjets_dr_min = 0.4
    reco_addjets_dr_max = 4.0
    #reco_addjets_dr_width = [0.4,0.6,1.0,2.0,4.0]

    nbins_reco_addjets_mass = 12 #4
    reco_addjets_m_min = 0
    reco_addjets_m_max = 400
    #reco_addjets_mass_width = [0.0,60.0,100.0,170.0,400.0]

    nbins_gen_addjets_dr = 4
    gen_addjets_dr_min = 0.4
    gen_addjets_dr_max = 4.0
    gen_addjets_dr_width = [0.4,0.6,1.0,2.0,4.0]

    nbins_gen_addjets_mass = 4
    gen_addjets_m_min = 0
    gen_addjets_m_max = 400
    gen_addjets_mass_width = [0.0,60.0,100.0,170.0,400.0]
    #gen_addjets_mass_width = [0.0,60.0,80.0,100.0,120.0,140.0,160.0,180.0,200.0,220.0,400.0]

    #Histograms for unfolding
    h_gen_addbjets_deltaR_nosel = [[0] for i in range(nChannel)]
    h_gen_addbjets_invMass_nosel = [[0] for i in range(nChannel)]
    h_njets = [[0] for i in range(nChannel)]
    h_nbjets = [[0] for i in range(nChannel)]
    h_reco_addjets_deltaR = [[0] for i in range(nChannel)]
    h_reco_addjets_invMass = [[0] for i in range(nChannel)]
    h_gen_addbjets_deltaR = [[0] for i in range(nChannel)]
    h_gen_addbjets_invMass = [[0] for i in range(nChannel)]
    h_respMatrix_deltaR = [[0] for i in range(nChannel)]
    h_respMatrix_invMass = [[0] for i in range(nChannel)]
    #h_respMatrix_invMass = [[0]*nStep for i in range(nChannel)]

    #Histograms of DNN input variables
    varlist = ut.getVarlist()
    xlabel = ut.getHistXlabel()
    h_hist = [[i for i in range(len(varlist))] for j in range(nChannel)]

    for iChannel in range(0,nChannel):
        for i in range(len(varlist)):
            histRange = []
            histRange = ut.getHistRange(varlist[i])
            h_hist[iChannel][i] = ROOT.TH1D(
                    'h_'+ varlist[i] + '_Ch' + str(iChannel) + process,'',
                    int(histRange[0]), float(histRange[1]), float(histRange[2])
                    )
            h_hist[iChannel][i].GetXaxis().SetTitle(xlabel[varlist[i]])
            h_hist[iChannel][i].GetYaxis().SetTitle("Entries")
            h_hist[iChannel][i].Sumw2()

        h_gen_addbjets_deltaR_nosel[iChannel] = ROOT.TH1D(
                "h_" + GEN_ADDBJETS_DELTAR_ + "_Ch" + str(iChannel) + "_nosel_" + process,
                "", nbins_gen_addjets_dr,
                #gen_addjets_dr_min, gen_addjets_dr_max
                array('d', gen_addjets_dr_width)
                )
        h_gen_addbjets_deltaR_nosel[iChannel].GetXaxis().SetTitle("#DeltaR_{b#bar{b}}")
        h_gen_addbjets_deltaR_nosel[iChannel].GetYaxis().SetTitle("Entries")
        h_gen_addbjets_deltaR_nosel[iChannel].Sumw2()

        h_gen_addbjets_invMass_nosel[iChannel] = ROOT.TH1D(
                "h_" + GEN_ADDBJETS_INVARIANT_MASS_ + "_Ch" + str(iChannel) + "_nosel_" + process,
                "", nbins_gen_addjets_mass,
                #gen_addjets_m_min, gen_addjets_m_max
                array('d', gen_addjets_mass_width)
                )
        h_gen_addbjets_invMass_nosel[iChannel].GetXaxis().SetTitle("m_{b#bar{b}}(GeV)")
        h_gen_addbjets_invMass_nosel[iChannel].GetYaxis().SetTitle("Entries")
        h_gen_addbjets_invMass_nosel[iChannel].Sumw2()

        h_njets[iChannel] = ROOT.TH1D(
                "h_" + RECO_NUMBER_OF_JETS_ + "_Ch" + str(iChannel) + "_S3_" + process,
                "",10, 0, 10
                )
        h_njets[iChannel].GetXaxis().SetTitle("Jet multiplicity")
        h_njets[iChannel].GetYaxis().SetTitle("Entries")
        h_njets[iChannel].Sumw2()

        h_nbjets[iChannel] = ROOT.TH1D(
                "h_" + RECO_NUMBER_OF_BJETS_ + "_Ch" + str(iChannel) + "_S3_" + process,
                "",10, 0, 10
                )
        h_nbjets[iChannel].GetXaxis().SetTitle("bJet multiplicity")
        h_nbjets[iChannel].GetYaxis().SetTitle("Entries")
        h_nbjets[iChannel].Sumw2()

        h_reco_addjets_deltaR[iChannel] = ROOT.TH1D(
                "h_" + RECO_ADDJETS_DELTAR_ + "_Ch" + str(iChannel) + "_S3_" + process,
                "", nbins_reco_addjets_dr,
                reco_addjets_dr_min, reco_addjets_dr_max
                #array('d', reco_addjets_dr_width)
                )
        h_reco_addjets_deltaR[iChannel].GetXaxis().SetTitle("#DeltaR_{b#bar{b}}")
        h_reco_addjets_deltaR[iChannel].GetYaxis().SetTitle("Entries")
        h_reco_addjets_deltaR[iChannel].Sumw2()

        h_reco_addjets_invMass[iChannel] = ROOT.TH1D(
                "h_" + RECO_ADDJETS_INVARIANT_MASS_ + "_Ch" + str(iChannel) + "_S3_" + process,
                "", nbins_reco_addjets_mass,
                reco_addjets_m_min, reco_addjets_m_max
                #array('d', reco_addjets_mass_width)
                )
        h_reco_addjets_invMass[iChannel].GetXaxis().SetTitle("m_{b#bar{b}}(GeV)")
        h_reco_addjets_invMass[iChannel].GetYaxis().SetTitle("Entries")
        h_reco_addjets_invMass[iChannel].Sumw2()

        h_gen_addbjets_deltaR[iChannel] = ROOT.TH1D(
                "h_" + GEN_ADDBJETS_DELTAR_ + "_Ch" + str(iChannel) + "_S3_" + process,
                "", nbins_gen_addjets_dr,
                #gen_addjets_dr_min, gen_addjets_dr_max
                array('d', gen_addjets_dr_width)
                )
        h_gen_addbjets_deltaR[iChannel].GetXaxis().SetTitle("#DeltaR_{b#bar{b}}")
        h_gen_addbjets_deltaR[iChannel].GetYaxis().SetTitle("Entries")
        h_gen_addbjets_deltaR[iChannel].Sumw2()

        h_gen_addbjets_invMass[iChannel] = ROOT.TH1D(
                "h_" + GEN_ADDBJETS_INVARIANT_MASS_ + "_Ch" + str(iChannel) + "_S3_" + process,
                "", nbins_gen_addjets_mass,
                #gen_addjets_m_min, gen_addjets_m_max
                array('d', gen_addjets_mass_width)
                )
        h_gen_addbjets_invMass[iChannel].GetXaxis().SetTitle("m_{b#bar{b}}(GeV)")
        h_gen_addbjets_invMass[iChannel].GetYaxis().SetTitle("Entries")
        h_gen_addbjets_invMass[iChannel].Sumw2()

        h_respMatrix_deltaR[iChannel] = ROOT.TH2D(
                "h_" + RESPONSE_MATRIX_DELTAR_ + "_Ch" + str(iChannel) + "_S3_" + process,"",
                nbins_reco_addjets_dr,
                reco_addjets_dr_min, reco_addjets_dr_max,
                #array('d', reco_addjets_dr_width),
                nbins_gen_addjets_dr,
                #gen_addjets_dr_min, gen_addjets_dr_max
                array('d', gen_addjets_dr_width)
                )
        h_respMatrix_deltaR[iChannel].GetXaxis().SetTitle("Reco. #DeltaR_{b#bar{b}}")
        h_respMatrix_deltaR[iChannel].GetYaxis().SetTitle("Gen. #DeltaR_{b#bar{b}}")
        h_respMatrix_deltaR[iChannel].Sumw2()

        h_respMatrix_invMass[iChannel] = ROOT.TH2D(
                "h_" + RESPONSE_MATRIX_INVARIANT_MASS_ + "_Ch" + str(iChannel) + "_S3_" + process,
                "", nbins_reco_addjets_mass,
                reco_addjets_m_min, reco_addjets_m_max,
                #array('d', reco_addjets_mass_width),
                nbins_gen_addjets_mass,#
                #gen_addjets_m_min, gen_addjets_m_max
                array('d', gen_addjets_mass_width)
                )
        h_respMatrix_invMass[iChannel].GetXaxis().SetTitle("Reco. m_{b#bar{b}}(GeV)")
        h_respMatrix_invMass[iChannel].GetYaxis().SetTitle("Gen. m_{b#bar{b}}(GeV)")
        h_respMatrix_invMass[iChannel].Sumw2()

    if ttbb == True :
        genchain = TChain("ttbbLepJets/gentree")
        genchain.Add("/data/users/seohyun/ntuple/hep2017/v808_noElSF/nosplit/"+process+".root")

        print "GENTREE RUN"
        for i in xrange(genchain.GetEntries()) :
            #if closureTest:
            #    if i%2 == 0 : continue
            ut.printProgress(i, genchain.GetEntries(), 'Progress:', 'Complete', 1, 50)
            genchain.GetEntry(i)
            addbjet1 = TLorentzVector()
            addbjet2 = TLorentzVector()
            addbjet1.SetPtEtaPhiE(genchain.addbjet1_pt, genchain.addbjet1_eta, genchain.addbjet1_phi, genchain.addbjet1_e)
            addbjet2.SetPtEtaPhiE(genchain.addbjet2_pt, genchain.addbjet2_eta, genchain.addbjet2_phi, genchain.addbjet2_e)

            gendR = addbjet1.DeltaR(addbjet2)
            genM = (addbjet1+addbjet2).M()

            if genchain.genchannel == muon_ch :
                h_gen_addbjets_deltaR_nosel[muon_ch].Fill(gendR,genchain.genweight)
                h_gen_addbjets_invMass_nosel[muon_ch].Fill(genM,genchain.genweight)
            elif genchain.genchannel == electron_ch :
                h_gen_addbjets_deltaR_nosel[electron_ch].Fill(gendR,genchain.genweight)
                h_gen_addbjets_invMass_nosel[electron_ch].Fill(genM,genchain.genweight)
            else : print("Error")

    print "\nTREE RUN"
    varlist = ut.getVarlist()
    nEvents = 0
    nEvt_isMatch_DNN = 0
    nEvt_isMatch_mindR = 0
    f_pred = open('pred.txt','w')
    for item in os.listdir(inputDir) :
        #print "Load file : "+str(inputDir)+'/'+str(item)
        df = pd.read_hdf(inputDir+'/'+item)
        str_query = 'csv1 > '+str(jet_CSV)+' and csv2 > '+str(jet_CSV)+' and njets >= 6 and nbjets >= 2'
        selEvent = df.query(str_query)
        selEvent.reset_index(drop=True, inplace=True)
        if len(selEvent.index) == 0 : continue
        nTotal = selEvent['event'].iloc[-1]

        jetCombi = selEvent.filter(varlist)
        scaler = StandardScaler()
        if len(jetCombi) is not 0 :
            inputset = np.array(jetCombi)
            inputset_sc = scaler.fit_transform(inputset)
            pred = model.predict(inputset_sc, batch_size = 2000)

        pred = pd.DataFrame(pred, columns=['background','signal'])
        #pred = pd.DataFrame(pred, columns=['signal'])
        #f_pred.write('Pred\n'+str(pred)+'\n'+str(type(pred)))
        #f_pred.write('SelEvent\n'+str(selEvent))
        selEvent = pd.concat([selEvent,pred], axis=1)
        #f_pred.write('SelEvent+Pred\n'+str(selEvent))
        idx = selEvent.groupby(['event'])['signal'].transform(max) == selEvent['signal']
        #f_pred.write('\n'+str(idx)+'\n'+str(selEvent[idx])+'\n')
        selEvent = selEvent[idx]
        selEvent.reset_index(drop=True, inplace=True)

        #selEvent.groupby('event').max('signal').reset_index(drop=True, inplace=True)
        f_pred.write("Groupby\n"+item+"\n"+str(selEvent))
        #groups = selEvent.groupby('event')
        for index, event in selEvent.iterrows() :
            #maxval = event[1][event[1]['signal'] == event[1]['signal'].max()]
            ut.printProgress(event['event'], nTotal, str(item)+':','Complete',1,25)

            eventweight = event['PUWeight']*event['genWeight']
            if not data :  eventweight *= event['lepton_SF']*event['jet_SF_CSV']

            passmuon = False
            passelectron = False
            if event['channel'] == 0 : passmuon = True
            if event['channel'] == 1 : passelectron = True

            njets = event['njets']
            nbjets = event['nbjets']

            gen_addbjet1 = TLorentzVector()
            gen_addbjet2 = TLorentzVector()
            gen_addbjet1.SetPtEtaPhiE(event['addbjet1_pt'],event['addbjet1_eta'],event['addbjet1_phi'],event['addbjet1_e'])
            gen_addbjet2.SetPtEtaPhiE(event['addbjet2_pt'],event['addbjet2_eta'],event['addbjet2_phi'],event['addbjet2_e'])

            gen_dR = gen_addbjet1.DeltaR(gen_addbjet2)
            gen_M = (gen_addbjet1+gen_addbjet2).M()

            reco_dR = 9999
            reco_M = 9999
            reco_addbjet1 = TLorentzVector(0,0,0,0)
            reco_addbjet2 = TLorentzVector(0,0,0,0)
            #additional bjets from DNN

            reco_addbjet1.SetPtEtaPhiE(event['pt1'],event['eta1'],event['phi1'],event['e1'])
            reco_addbjet2.SetPtEtaPhiE(event['pt2'],event['eta2'],event['phi2'],event['e2'])

            reco_dR = reco_addbjet1.DeltaR(reco_addbjet2)
            reco_M = (reco_addbjet1+reco_addbjet2).M()

            #f_pred.write('Pred : '+str(maxval)+'\n')
            #f_pred.write('Score\n'+str(event[1])+'\n')
            #f_pred.write('jet 1 : '+str(reco_addbjet1.Pt())+' jet 2 : '+str(reco_addbjet2.Pt())+'\n')
            #f_pred.write('genjet 1 : '+str(gen_addbjet1.Pt())+' genjet2 : '+str(gen_addbjet2.Pt())+'\n')
            #f_pred.write('reco dR : '+str(reco_addbjet1.DeltaR(reco_addbjet2))+'gen dR : '+str(gen_addbjet1.DeltaR(gen_addbjet2))+'\n')

            passchannel = -999
            passcut = 0

            #matching ratio
            isMatch_DNN = False
            isMatch_DNN = (reco_addbjet1.DeltaR(gen_addbjet1) < 0.5 and reco_addbjet2.DeltaR(gen_addbjet2) < 0.5) or (reco_addbjet1.DeltaR(gen_addbjet2) < 0.5 and reco_addbjet2.DeltaR(gen_addbjet1) < 0.5)
            if passmuon == True and passelectron == False : passchannel = muon_ch
            elif passmuon == False and passelectron == True : passchannel = electron_ch
            else : print "Error!"
            if isMatch_DNN : nEvt_isMatch_DNN += 1
            nEvents += 1

            if closureTest:
                if index%2 == 1:
                    h_njets[passchannel].Fill(njets, eventweight)
                    h_nbjets[passchannel].Fill(nbjets, eventweight)
                    h_reco_addjets_deltaR[passchannel].Fill(reco_dR, eventweight)
                    h_reco_addjets_invMass[passchannel].Fill(reco_M, eventweight)
                    h_gen_addbjets_deltaR[passchannel].Fill(gen_dR, eventweight)
                    h_gen_addbjets_invMass[passchannel].Fill(gen_M, eventweight)
                else:
                    h_respMatrix_deltaR[passchannel].Fill(reco_dR, gen_dR, eventweight)
                    h_respMatrix_invMass[passchannel].Fill(reco_M, gen_M, eventweight)
            else:
                h_njets[passchannel].Fill(njets, eventweight)
                h_nbjets[passchannel].Fill(nbjets, eventweight)
                h_reco_addjets_deltaR[passchannel].Fill(reco_dR, eventweight)
                h_reco_addjets_invMass[passchannel].Fill(reco_M, eventweight)
                for index, value in enumerate(varlist):
                    h_hist[passchannel][index].Fill(event[value], eventweight)
                if ttbb:
                    h_gen_addbjets_deltaR[passchannel].Fill(gen_dR, eventweight)
                    h_gen_addbjets_invMass[passchannel].Fill(gen_M, eventweight)
                    h_respMatrix_deltaR[passchannel].Fill(reco_dR, gen_dR, eventweight)
                    h_respMatrix_invMass[passchannel].Fill(reco_M, gen_M, eventweight)

    if ttbb:
        matching_DNN = 0.0
        #matching_mindR = 0.0
        if nEvents is not 0 :
            matching_DNN_able = float(nEvt_isMatch_DNN) / float(nMatchable)
            matching_DNN = float(nEvt_isMatch_DNN) / float(nEvents)
            #matching_mindR = float(nEvt_isMatch_mindR) / float(nEvents)
        #print "\nSelected Events / Total Events : "+str(nEvents)+"/"+str(nTotal)
        print "Matching ratio with matchable events from DNN : "+str(matching_DNN_able)+"("+str(nEvt_isMatch_DNN)+"/"+str(nMatchable)+")"
        print "Matching ratio with step 3 events from DNN : "+str(matching_DNN)+"("+str(nEvt_isMatch_DNN)+"/"+str(nEvents)+")"
        #print "Matching Ratio from minimun dR : "+str(matching_mindR)+"("+str(nEvt_isMatch_mindR)+"/"+str(nEvents)+")"
        f_ratio = open('ratio.txt','a')
        f_ratio.write(modelfile)
        f_ratio.write("\nMatching ratio with matchable events from DNN: "+str(matching_DNN_able)+"("+str(nEvt_isMatch_DNN)+"/"+str(nMatchable)+")\n")
        f_ratio.close()

    for iChannel in range(nChannel) :
        h_njets[iChannel].AddBinContent(10,h_njets[iChannel].GetBinContent(11))
        h_nbjets[iChannel].AddBinContent(10,h_nbjets[iChannel].GetBinContent(11))
        h_reco_addjets_deltaR[iChannel].AddBinContent(nbins_reco_addjets_dr, h_reco_addjets_deltaR[iChannel].GetBinContent(nbins_reco_addjets_dr+1))
        h_reco_addjets_invMass[iChannel].AddBinContent(nbins_reco_addjets_mass, h_reco_addjets_invMass[iChannel].GetBinContent(nbins_reco_addjets_mass+1))
        h_gen_addbjets_deltaR[iChannel].AddBinContent(nbins_gen_addjets_dr, h_gen_addbjets_deltaR[iChannel].GetBinContent(nbins_gen_addjets_dr+1))
        h_gen_addbjets_invMass[iChannel].AddBinContent(nbins_gen_addjets_mass, h_gen_addbjets_invMass[iChannel].GetBinContent(nbins_gen_addjets_mass+1))

        for index, value in enumerate(varlist):
            tmp = ut.getHistRange(value)
            h_hist[iChannel][index].AddBinContent(tmp[0], h_hist[iChannel][index].GetBinContent(tmp[0]+1))
            h_hist[iChannel][index].AddBinContent(1, h_hist[iChannel][index].GetBinContent(0))
            h_hist[iChannel][index].ClearUnderflowAndOverflow()

        for iXaxis in range(1, nbins_reco_addjets_dr+1) :
            tmp = h_respMatrix_deltaR[iChannel].GetBinContent(iXaxis, nbins_gen_addjets_dr)+h_respMatrix_deltaR[iChannel].GetBinContent(iXaxis, nbins_gen_addjets_dr+1)
            h_respMatrix_deltaR[iChannel].SetBinContent(iXaxis, nbins_gen_addjets_dr, tmp)
        for iYaxis in range(1, nbins_gen_addjets_dr+1) :
            tmp = h_respMatrix_deltaR[iChannel].GetBinContent(nbins_reco_addjets_dr, iYaxis)+h_respMatrix_deltaR[iChannel].GetBinContent(nbins_reco_addjets_dr+1, iYaxis)
            h_respMatrix_deltaR[iChannel].SetBinContent(nbins_reco_addjets_dr, iYaxis, tmp)

        for iXaxis in range(1, nbins_reco_addjets_mass+1) :
            tmp = h_respMatrix_invMass[iChannel].GetBinContent(iXaxis, nbins_gen_addjets_mass)+h_respMatrix_invMass[iChannel].GetBinContent(iXaxis, nbins_gen_addjets_mass+1)
            h_respMatrix_invMass[iChannel].SetBinContent(iXaxis, nbins_gen_addjets_mass, tmp)
        for iYaxis in range(1, nbins_gen_addjets_mass+1) :
            tmp = h_respMatrix_invMass[iChannel].GetBinContent(nbins_reco_addjets_mass, iYaxis)+h_respMatrix_invMass[iChannel].GetBinContent(nbins_reco_addjets_mass+1, iYaxis)
            h_respMatrix_invMass[iChannel].SetBinContent(nbins_reco_addjets_mass, iYaxis,tmp)

        tmp = h_respMatrix_deltaR[iChannel].GetBinContent(nbins_reco_addjets_dr+1,nbins_gen_addjets_dr+1)+h_respMatrix_deltaR[iChannel].GetBinContent(nbins_reco_addjets_dr,nbins_gen_addjets_dr)
        h_respMatrix_deltaR[iChannel].SetBinContent(nbins_reco_addjets_dr,nbins_gen_addjets_dr,tmp)
        tmp = h_respMatrix_invMass[iChannel].GetBinContent(nbins_reco_addjets_mass+1,nbins_gen_addjets_mass+1)+h_respMatrix_invMass[iChannel].GetBinContent(nbins_reco_addjets_mass,nbins_gen_addjets_mass)
        h_respMatrix_invMass[iChannel].SetBinContent(nbins_reco_addjets_mass,nbins_gen_addjets_mass,tmp)

        h_njets[iChannel].ClearUnderflowAndOverflow()
        h_nbjets[iChannel].ClearUnderflowAndOverflow()
        h_reco_addjets_deltaR[iChannel].ClearUnderflowAndOverflow()
        h_reco_addjets_invMass[iChannel].ClearUnderflowAndOverflow()
        h_gen_addbjets_deltaR[iChannel].ClearUnderflowAndOverflow()
        h_gen_addbjets_invMass[iChannel].ClearUnderflowAndOverflow()
        h_respMatrix_deltaR[iChannel].ClearUnderflowAndOverflow()
        h_respMatrix_invMass[iChannel].ClearUnderflowAndOverflow()

    f = TFile("/data/users/seohyun/ntuple/hep2017/v808/nosplit/"+process+".root")

    h_evt = f.Get("ttbbLepJets/EventInfo")
    f_out.cd()
    h_evt.Write()
    f_out.Write()
    f_out.Close()
    f_pred.close()

    timer.Stop()
    realtime = timer.RealTime()
    cputime = timer.CpuTime()
    print("Real Time : {0:6.2f} seconds, CPU Time : {1:6.2f} seconds").format(realtime,cputime)