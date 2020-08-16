# -*- coding: utf-8 -*-
"""
Created on Sun Aug 16 18:14:24 2020

@author: albye
"""

# -*- coding: utf-8 -*-
"""
Created on Wed Jul  8 10:27:31 2020

@author: albye

"""
import Metrica_IO as mio
import Metrica_Viz as mviz
import Metrica_Velocities as mvel
import Metrica_PitchControl as mpc
import numpy as np
import math
import pandas as pd
import Metrica_EPV as mepv

#make this where you have saved the data
DATADIR = 'C:/Users/albye/Documents/'


# let's look at sample match 2
game_id = 2 

# read in the event data
events = mio.read_event_data(DATADIR,game_id)

# read in tracking data
tracking_home = mio.tracking_data(DATADIR,game_id,'Home')
tracking_away = mio.tracking_data(DATADIR,game_id,'Away')

# Convert positions from metrica units to meters (note change in Metrica's coordinate system since the last lesson)
tracking_home = mio.to_metric_coordinates(tracking_home)
tracking_away = mio.to_metric_coordinates(tracking_away)
events = mio.to_metric_coordinates(events)

# reverse direction of play in the second half so that home team is always attacking from right->left
tracking_home,tracking_away,events = mio.to_single_playing_direction(tracking_home,tracking_away,events)

# Calculate player velocities
tracking_home = mvel.calc_player_velocities(tracking_home,smoothing=True)
tracking_away = mvel.calc_player_velocities(tracking_away,smoothing=True)


#get the times of passes made by the home team
idx=(events['Team']=='Home') & (events['Type']=='PASS')
home_passes_times=events[idx][['Start Time [s]','From']]
home_passes_times.index=range(len(home_passes_times))

#variable to determine how long before the pass we look for a run
run_time=2
#have to maintain the run for at least 1 second 
run_window = 1*25
run_threshold = 4 # minimum speed to be defined as a sprint (m/s)

#set up array with the times in the 2-second window before each pass
#each element of this list will be an array of the timestamps up to 2 secs before run made
run_windows=[]
for pass_time in home_passes_times['Start Time [s]']:
    temp_array=np.linspace(pass_time-run_time,pass_time,25*run_time+1)
    #round it
    temp_array=np.around(temp_array,2)
    run_windows.append(temp_array)

#keep appending arrays from run_windows together until there's no overlap
#then put these new arrays into disjoint_run_windows
disjoint_run_windows=[]
for i in range(1,len(run_windows)):
    if np.isin(run_windows[i],run_windows[i-1]).sum() !=  0:
        run_windows[i]=np.append(run_windows[i-1],run_windows[i])
    else:
        disjoint_run_windows.append(run_windows[i-1])

#manually add on last element of run_windows to disjoint_run_windows
disjoint_run_windows.append(run_windows[len(run_windows)-1])

#get average time taken to play pass for home team  
events['time_taken']=events['End Time [s]']-events['Start Time [s]']
idx=(events['Team']=='Home') & (events['Type']=='PASS')
avg_pass_time=events[idx]['time_taken'].mean()

#new method for counting runs
#set up df
home_players = np.unique( [ c.split('_')[1] for c in tracking_home.columns if c[:4] == 'Home' ] )
home_summary = pd.DataFrame(index=home_players)
#empty list to store number of runs made by all players
nruns=[]
for player in home_summary.index: 
#loop through each time each pass was played
    #temporary variable for each player to count no.runs they make
    player_runs=0
    column = 'Home_' + player + '_speed'
    column_x = 'Home_' + player + '_x' # x position
    column_y = 'Home_' + player + '_y' # y position
    for window in disjoint_run_windows:
        #get the speed of the player during each window
        idx=(tracking_home['Time [s]']>=window[0]) & (tracking_home['Time [s]']<= window[len(window)-1])
        speed_b4_pass=tracking_home[idx][[column,'Time [s]']]
        #filter to when player running at desired speed 
        runs_b4_pass=speed_b4_pass[speed_b4_pass[column]>=run_threshold]
        #if player running at high enough speed for long enough just before pass, count it as a run
        if len(runs_b4_pass)>=run_window:
            #get end time of run and find time of pass played closest to that time
            end_time=runs_b4_pass.iloc[len(runs_b4_pass)-1]['Time [s]']
            time_diff=abs(home_passes_times['Start Time [s]']-end_time)
            idx=time_diff[time_diff==time_diff.min()].index[0]
            #get time our chosen pass was played
            pass_time=home_passes_times.iloc[idx]['Start Time [s]']
            #get player who played the pass
            #so we can make sure we ignore a player's run just before their passes
            passer=home_passes_times.iloc[idx]['From']
            #remove the 'Player' bit at the start of the string
            passer=passer.replace('Player','')
            #get position this pass was played from
            pass_start_pos=np.array([float(events.loc[(events['Start Time [s]']==pass_time) & (events['Type']=='PASS')]['Start X']),float(events.loc[(events['Start Time [s]']==pass_time) & (events['Type']=='PASS')]['Start Y'])])
            #get end location of player's run 
            end_idx=tracking_home.loc[tracking_home['Time [s]']==end_time].index[0]-1
            #extrapolate the end location of the run a bit
            #i.e. get their location avg_pass_time after they finish their run
            #if player is running, would expect ball to be played a bit in front of them
            end_idx=end_idx+math.ceil(avg_pass_time/0.04)
            end_location=(tracking_home[column_x].iloc[end_idx],tracking_home[column_y].iloc[end_idx])
            #get start location of run
            start_idx=runs_b4_pass.index[0]-1
            start_location=(tracking_home[column_x].iloc[start_idx],tracking_home[column_y].iloc[start_idx])
            #only count the (forward) run is pass is in oppo half and run ends in oppo half
            if pass_start_pos[0] <= 0 and end_location[0] <= 0 and passer!=player and end_location[0]<start_location[0]:
                counter=1
            else:
                counter=0
        else:
            counter=0
        player_runs=player_runs+counter
    #once gone through each pass for a certain player, append their no.runs to nruns list
    nruns.append(player_runs)
home_summary['# runs'] = nruns
      
#now plot some of these runs
#the player you want to plot the runs for
player = '9'
column = 'Home_' + player + '_speed' #speed
column_x = 'Home_' + player + '_x' # x position
column_y = 'Home_' + player + '_y' # y position
fig,ax = mviz.plot_pitch()
player_runs=0
#also make a df to store some details about the runs to produce some clips
run_details=pd.DataFrame(columns=['start_frame','start_x','start_y','end_x','end_y','end_frame','end_time'])
for window in disjoint_run_windows:
    #get the speed of the player during each window
    idx=(tracking_home['Time [s]']>=window[0]) & (tracking_home['Time [s]']<= window[len(window)-1])
    speed_b4_pass=tracking_home[idx][[column,'Time [s]']]
    #filter to when player running at desired speed 
    runs_b4_pass=speed_b4_pass[speed_b4_pass[column]>=run_threshold]
    if len(runs_b4_pass) >= run_window:
        #get end time of run and find time of pass played closest to that time
        end_time=runs_b4_pass.iloc[len(runs_b4_pass)-1]['Time [s]']
        time_diff=abs(home_passes_times['Start Time [s]']-end_time)
        idx=time_diff[time_diff==time_diff.min()].index[0]
        pass_time=home_passes_times.iloc[idx]['Start Time [s]']
        #get player who played the pass
        #so we can make sure we ignore a player's run just before their passes
        passer=home_passes_times.iloc[idx]['From']
        #remove the 'Player' bit at the start of the string
        passer=passer.replace('Player','')
        #get position this pass was played from
        pass_start_pos=np.array([float(events.loc[(events['Start Time [s]']==pass_time) & (events['Type']=='PASS')]['Start X']),float(events.loc[(events['Start Time [s]']==pass_time) & (events['Type']=='PASS')]['Start Y'])])
        #get end location of player's run 
        end_idx=tracking_home.loc[tracking_home['Time [s]']==pass_time].index[0]-1
        #extrapolate the end location of the run a bit
        #i.e. get their location avg_pass_time after they finish their run
        #if player is running, would expect ball to be played a bit in front of them
        end_idx=end_idx+math.ceil(avg_pass_time/0.04)
        end_location=(tracking_home[column_x].iloc[end_idx],tracking_home[column_y].iloc[end_idx])
        #get start location of run
        start_idx=runs_b4_pass.index[0]-1
        start_location=(tracking_home[column_x].iloc[start_idx],tracking_home[column_y].iloc[start_idx])
        #only count&plot the run is pass is in oppo half and run ends in oppo half
        if pass_start_pos[0] <= 0 and end_location[0] <= 0 and passer!=player and end_location[0]<start_location[0]:
            counter=1
            #start idx also fthe frame where the run starts
            ax.plot(tracking_home[column_x].iloc[start_idx],tracking_home[column_y].iloc[start_idx],'ro')
            ax.plot(tracking_home[column_x].iloc[start_idx:end_idx],tracking_home[column_y].iloc[start_idx:end_idx],'r')
            ax.plot()
            #get the frame the pass was made
            pass_frame=np.array(events.loc[events['Start Time [s]']==pass_time]['End Frame'])[0]
            #annotate the runs with the start&end frame so easy to identify run and make a video
            ax.text(tracking_home[column_x].iloc[start_idx]+0.5,tracking_home[column_y].iloc[start_idx]+0.5,start_idx-1,fontsize=7)
            #add some details to the df
            #set up row to add into df (which contains start and end location of run)
            row=[start_idx,start_location[0],start_location[1],end_location[0],end_location[1],end_idx,end_time]
            #make a temp df with these details as a row (T transpose from 4*1 to 1*4)
            temp_df=pd.DataFrame(row).T
            #change column names so can append to big df
            temp_df.columns=['start_frame','start_x','start_y','end_x','end_y','end_frame','end_time']
            #append to big df
            run_details=run_details.append(temp_df)
        else:
            counter=0
    else:
        counter=0
    player_runs=player_runs+counter
        
#now to evaluate the value added of the run
#at the moment of the pass, get pitch control*epv at end location of players run
#compare this to pitch control * epv at start location of player's run (with velocity 0)
# first get pitch control model parameters
params = mpc.default_model_params()
# find goalkeepers for offside calculation
GK_numbers = [mio.find_goalkeeper(tracking_home),mio.find_goalkeeper(tracking_away)]
#get EPV surface
home_attack_direction = mio.find_playing_direction(tracking_home,'Home') # 1 if shooting left-right, else -1
EPV = mepv.load_EPV_grid(DATADIR+'/EPV_grid.csv')
#set up empty list to add avg value added from off ball runs for each player
avg_value_added=[]
#also make a df to store some details about value added for each run
val_added_details=pd.DataFrame(columns=['player','start_frame','val_added','end_frame','end_time','pass_time','event_id'])

for player in home_summary.index:
    column = 'Home_' + player + '_speed'
    column_x = 'Home_' + player + '_x' # column with player's x position
    column_y = 'Home_' + player + '_y' # column with player's y position
    vel_x = 'Home_' + player + '_vx'
    vel_y = 'Home_' + player + '_vy'
    #set up empty array to add value added of each run
    run_values=np.array([])
    for window in disjoint_run_windows:
        #get the speed of the player during each window
        idx=(tracking_home['Time [s]']>=window[0]) & (tracking_home['Time [s]']<= window[len(window)-1])
        speed_b4_pass=tracking_home[idx][[column,'Time [s]']]
        #filter to when player running at desired speed 
        runs_b4_pass=speed_b4_pass[speed_b4_pass[column]>=run_threshold]
        #if player running at high enough speed for long enough just before pass,investigate further
        if len(runs_b4_pass)>=run_window:
            #get end time of run and find time of pass played closest to that time
            end_time=runs_b4_pass.iloc[len(runs_b4_pass)-1]['Time [s]']
            #get time diff between end time of run and all passes played
            time_diff=abs(home_passes_times['Start Time [s]']-end_time)
            #the pass we will use is the pass played closest to the end time of the run
            idx=time_diff[time_diff==time_diff.min()].index[0]
            pass_time=home_passes_times.iloc[idx]['Start Time [s]']
            #get event_id to try and feed into calculating space created?
            event_id=events.loc[events['Start Time [s]']==pass_time].index[0]
            #get player who played the pass
            #so we can make sure we ignore a player's run just before their passes
            passer=home_passes_times.iloc[idx]['From']
            #remove the 'Player' bit at the start of the string
            passer=passer.replace('Player','')
            #get position this pass was played from
            pass_start_pos=np.array([float(events.loc[(events['Start Time [s]']==pass_time) & (events['Type']=='PASS')]['Start X']),float(events.loc[(events['Start Time [s]']==pass_time) & (events['Type']=='PASS')]['Start Y'])])
            #get end location of player's run 
            end_idx=tracking_home.loc[tracking_home['Time [s]']==pass_time].index[0]-1
            #extrapolate the end location of the run a bit
            #i.e. get their location avg_pass_time after they finish their run
            #if player is running, would expect ball to be played a bit in front of them
            end_idx=end_idx+math.ceil(avg_pass_time/0.04)
            end_location=(tracking_home[column_x].iloc[end_idx],tracking_home[column_y].iloc[end_idx])
            #get start location of run
            start_idx=runs_b4_pass.index[0]-1
            start_location=(tracking_home[column_x].iloc[start_idx],tracking_home[column_y].iloc[start_idx])
            #only count the (forward) run is pass is in oppo half and run ends in oppo half
            if pass_start_pos[0] <= 0 and end_location[0] <= 0 and passer!=player and end_location[0]<start_location[0]:
                #get player's location at time pass made/'end of run' (extapolate more?)
                pass_target_pos=np.array(end_location)
                #get the frame where the pass was made
                pass_frame=np.array(events.loc[events['Start Time [s]']==pass_time]['Start Frame'])[0]
                #need to do this for the pitch control calculations
                attacking_players = mpc.initialise_players(tracking_home.loc[pass_frame],'Home',params, GK_numbers[0])
                defending_players = mpc.initialise_players(tracking_away.loc[pass_frame],'Away',params, GK_numbers[1])
                #get pitch control at end location
                Patt_end = mpc.calculate_pitch_control_at_target(pass_target_pos, attacking_players, defending_players, pass_start_pos, params)[0]
                #also get epv at end location of run
                epv_end=mepv.get_EPV_at_location(end_location, EPV, home_attack_direction)
                #now get pitch control at the location where player started his run 
                start_idx=runs_b4_pass.index[0]-1
                start_location=(tracking_home[column_x].iloc[start_idx],tracking_home[column_y].iloc[start_idx])
                pass_target_pos=np.array(start_location)
                #pass_start_pos stays the same as want to compare value added of run made
                #at time of pass, change player's location to where he started his run
                #also change velocity to zero
                #create copy of tracking_home, so don't change original df
                tracking_home_copy=tracking_home.copy() 
                tracking_home_copy.loc[pass_frame,column_x]=tracking_home[column_x].iloc[start_idx]
                tracking_home_copy.loc[pass_frame,column_y]=tracking_home[column_y].iloc[start_idx]
                #also change velocity/speed to zero
                tracking_home_copy.loc[pass_frame,vel_x]=0
                tracking_home_copy.loc[pass_frame,vel_y]=0
                tracking_home_copy.loc[pass_frame,column]=0
                #reinitialise attacking players
                attacking_players = mpc.initialise_players(tracking_home_copy.loc[pass_frame],'Home',params, GK_numbers[0])
                #get pitch control at start location of players run
                Patt_start = mpc.calculate_pitch_control_at_target(pass_target_pos, attacking_players, defending_players, pass_start_pos, params)[0]
                #calculate epv at the start location of the player's run
                epv_start=mepv.get_EPV_at_location(start_location, EPV, home_attack_direction)
                #get value added of run
                value_added=(Patt_end*epv_end)-(Patt_start*epv_start)
                #append it to run_values array
                run_values=np.append(run_values,value_added)
                #remove copy of tracking_home 
                del tracking_home_copy
                #set up row to add into df (which contains start and end location of run)
                row=[player,start_idx,value_added,end_idx,end_time,pass_time,event_id]
                #make a temp df with these details as a row (T transpose from 4*1 to 1*4)
                temp_df=pd.DataFrame(row).T
                #change column names so can append to big df
                temp_df.columns=['player','start_frame','val_added','end_frame','end_time','pass_time','event_id']
                #append to big df
                val_added_details=val_added_details.append(temp_df)
    #get the average value added from all runs and append it to the list
    avg_value_added.append(run_values.mean())
home_summary['avg_run_val_added']=avg_value_added
              
    
        
#making clips of the runs
PLOTDIR = 'C:/Users/albye/Documents/tracking analysis/clips'
#start frame to get video from
start=58390 
#end frame you want video to play till
end=58448
#name of the file you want to save the clip to
file_name='10_58390'
mviz.save_match_clip(tracking_home.iloc[start:end],tracking_away.iloc[start:end],PLOTDIR,fname=file_name,include_player_velocities=True)
