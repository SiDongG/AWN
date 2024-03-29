import numpy as np
from numpy import genfromtxt
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from sklearn.cluster import DBSCAN
from sklearn import metrics
import pandas as pd
from pyquaternion import Quaternion
from numpy.linalg import norm
import math

from IMU import iframe

class client():
    def __init__(self, IMUdata, ip_address):   
        self.id = ip_address
        self.ClusterID = 0
        self.x = -1
        self.y = -1
        self.x_velocity= -1
        self.y_velocity = -1
        self.z_velocity = -1
        self.x_orient=0
        self.y_orient=0
        self.z_orient=0
        self.quaternion=Quaternion(1,0,0,0)
        self.x_estimate = -1
        self.y_estimate = -1
        self.firstFrame = True
        self.imuFrame = IMUdata
        self.x_accel_offset = 0
        self.y_accel_offset = 0
        self.z_accel_offset = 0
        self.imuFramePrev = iframe([-1,-1,-1,-1,-1,-1])
    
    def update_imu_data(self, imu_data):
        self.recalibrate()
        self.imuFramePrev = self.imuFrame
        self.imuFrame = imu_data
    def __str__(self):
        return f'\n #### Client {self.id} ####\ncurrentFrame\n{self.imuFrame}\npreviousFrame{self.imuFramePrev }'
    def recalibrate(self):
        if self.firstFrame:
            self.x_accel_offset = self.imuFrame.accel_x
            self.y_accel_offset = self.imuFrame.accel_y
            self.z_accel_offset = self.imuFrame.accel_z
            self.firstFrame = False
        self.imuFrame.accel_x -= self.x_accel_offset
        self.imuFrame.accel_y -= self.y_accel_offset
        self.imuFrame.accel_z -= self.z_accel_offset


def getData(data_df):
    data = np.array([])
    unique_value = data_df.iloc[:,1].value_counts().index
    sorted_list = sorted(unique_value)
    frame_num = sorted_list[-2]
    print(frame_num)
    df_filtered = data_df[data_df.iloc[:,1]==frame_num]

    return df_filtered

def quaternion_mult(q,r):
    return [r[0]*q[0]-r[1]*q[1]-r[2]*q[2]-r[3]*q[3],
            r[0]*q[1]+r[1]*q[0]-r[2]*q[3]+r[3]*q[2],
            r[0]*q[2]+r[1]*q[3]+r[2]*q[0]-r[3]*q[1],
            r[0]*q[3]-r[1]*q[2]+r[2]*q[1]+r[3]*q[0]]

def Direction_Correction(point,q):
    r = [0]+point
    q_conj = [q[0],-1*q[1],-1*q[2],-1*q[3]]
    return quaternion_mult(quaternion_mult(q,r),q_conj)[1:]

def quaternion_to_euler(client):
    """
    Convert a quaternion to Euler angles (roll, pitch, yaw) in radians.
    Parameters:
        q (numpy.ndarray): A quaternion represented as a four-element numpy array [w, x, y, z].
    Returns:
        numpy.ndarray: A three-element numpy array [roll, pitch, yaw] in radians.
    """
    # Normalize the quaternion
    q = client.quaternion
    g = np.array([q[0],q[1],q[2],q[3]])
    q_norm = q / norm(g)

    # Extract the components of the quaternion
    w, x, y, z = q_norm

    # Calculate the roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    # Calculate the pitch (y-axis rotation)
    sinp = 2.0 * (w * y - z * x)
    if np.abs(sinp) >= 1:
        pitch = np.copysign(np.pi / 2, sinp)  # Use 90 degrees if out of range
    else:
        pitch = np.arcsin(sinp)

    # Calculate the yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)

    # return np.array([roll, pitch, yaw])

    # update client.x_orient, client.y_orient
    client.x_orient = roll
    client.y_orient = pitch





def trackOrientation(frame_time,client):
    beta = 1
    zeta = 0
    # 9-D Madgwick Filter 
    q = client.quaternion
    h = q * (Quaternion(0, client.imuFrame.mag_x, client.imuFrame.mag_y, client.imuFrame.mag_z)*q.conj())
    b = np.array([0, norm(h[1:3]), 0, h[3]])
    f = np.array([
            2*(q[1]*q[3] - q[0]*q[2]) - client.imuFrame.accel_x,
            2*(q[0]*q[1] + q[2]*q[3]) - client.imuFrame.accel_y,
            2*(0.5 - q[1]**2 - q[2]**2) - client.imuFrame.accel_z,
            2*b[1]*(0.5 - q[2]**2 - q[3]**2) + 2*b[3]*(q[1]*q[3] - q[0]*q[2]) - client.imuFrame.mag_x,
            2*b[1]*(q[1]*q[2] - q[0]*q[3]) + 2*b[3]*(q[0]*q[1] + q[2]*q[3]) - client.imuFrame.mag_y,
            2*b[1]*(q[0]*q[2] + q[1]*q[3]) + 2*b[3]*(0.5 - q[1]**2 - q[2]**2) - client.imuFrame.mag_z
        ])
    j = np.array([
        [-2*q[2],                  2*q[3],                  -2*q[0],                  2*q[1]],
        [2*q[1],                   2*q[0],                  2*q[3],                   2*q[2]],
        [0,                        -4*q[1],                 -4*q[2],                  0],
        [-2*b[3]*q[2],             2*b[3]*q[3],             -4*b[1]*q[2]-2*b[3]*q[0], -4*b[1]*q[3]+2*b[3]*q[1]],
        [-2*b[1]*q[3]+2*b[3]*q[1], 2*b[1]*q[2]+2*b[3]*q[0], 2*b[1]*q[1]+2*b[3]*q[3],  -2*b[1]*q[0]+2*b[3]*q[2]],
        [2*b[1]*q[2],              2*b[1]*q[3]-4*b[3]*q[1], 2*b[1]*q[0]-4*b[3]*q[2],  2*b[1]*q[1]]
    ])
    step = j.T.dot(f)
    step /= norm(step)
    gyroscopeQuat = Quaternion(0, client.imuFrame.gyro_x, client.imuFrame.gyro_y, client.imuFrame.gyro_z)
    stepQuat = Quaternion(step.T[0], step.T[1], step.T[2], step.T[3])
    gyroscopeQuat = gyroscopeQuat + (q.conj() * stepQuat) * 2 * frame_time * zeta * -1
    qdot = (q * gyroscopeQuat) * 0.5 - beta * step.T

    q += qdot * client.samplePeriod
    client.quaternion = Quaternion(q / norm(q))
    return

def trackOrientation6D(frame_time,client):
    zeta = 0
    beta = 1
    # 6-D Madgwick Filter
    q = client.quaternion
    f = np.array([
            2*(q[1]*q[3] - q[0]*q[2]) - client.imuFrame.accel_x,
            2*(q[0]*q[1] + q[2]*q[3]) - client.imuFrame.accel_y,
            2*(0.5 - q[1]**2 - q[2]**2) - client.imuFrame.accel_z
        ])
    j = np.array([
        [-2*q[2], 2*q[3], -2*q[0], 2*q[1]],
        [2*q[1], 2*q[0], 2*q[3], 2*q[2]],
        [0, -4*q[1], -4*q[2], 0]
    ])
    step = j.T.dot(f)
    step /= norm(step) 

    qdot = (q * Quaternion(0, client.imuFrame.gyro_x, client.imuFrame.gyro_y, client.imuFrame.gyro_z)) * 0.5 - beta * step.T

    q += qdot * frame_time
    g = np.array([q[0],q[1],q[2],q[3]])
    q = q/norm(g)
    client.quaternion = q

def getVelocity(frame_time,client1,client2):
    client1.x_velocity = 0.5*(client1.imuFrame.accel_x+client1.imuFramePrev.accel_x)*frame_time
    client1.y_velocity = 0.5*(client1.imuFrame.accel_y+client1.imuFramePrev.accel_y)*frame_time
    client1.z_velocity = 0.5*(client1.imuFrame.accel_z+client1.imuFramePrev.accel_z)*frame_time
    client2.x_velocity = 0.5*(client2.imuFrame.accel_x+client2.imuFramePrev.accel_x)*frame_time
    client2.y_velocity = 0.5*(client2.imuFrame.accel_y+client2.imuFramePrev.accel_y)*frame_time
    client2.z_velocity = 0.5*(client2.imuFrame.accel_z+client2.imuFramePrev.accel_z)*frame_time
    return 


def beamform_angle(Theta, client1):
    angle_orient = math.atan2(client1.y_orient, client1.x_orient)  # orient of the client

    ori_range_lowerbound = angle_orient - math.pi / 2
    ori_range_upperbound = angle_orient + math.pi / 2
    beamBool = False
    if Theta >= ori_range_lowerbound and Theta <= ori_range_upperbound:
        print('Can beamform')
        beamBool = True
        BF_angle = abs(Theta - angle_orient)
        angle_from_lowerbound = Theta - ori_range_lowerbound
        # beamform angle is some radian to the left or right of the center, so BF_angle in [0,pi/2]
        if angle_from_lowerbound < math.pi/2:
            print('Right side of center')
        if angle_from_lowerbound > math.pi/2:
            print('Left side of center')
            BF_angle = Theta - ori_range_lowerbound - math.pi/2
    else:
        print('Cannot beamform')
        BF_angle = 100  #  does not mean angle is 100, mean to be set as AUTO mode for router

    return beamBool, BF_angle  # in radian


class rframe():
	
    def __init__(self, frame_num, data, clients, prev_frame, start_time):   
        self.frame_num = frame_num
        self.data = data #csv data, might need to be converted to pandas object
        self.clients = clients # array of clients with IMU data
        self.prev_frame = prev_frame
        self.frame_start_time = start_time

    def getCluster(self):
		### preform DBscan, eliminate noise ##
        data2 = self.data
        data2 = data2.iloc[:,3:6]
        db = DBSCAN(eps=0.3, min_samples=25).fit(data2)
        labels = db.labels_
        n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)  # Number of Clusters, Label 0-N
        core_samples_mask = np.zeros_like(labels, dtype=bool)
        core_samples_mask[db.core_sample_indices_] = True
        return labels,n_clusters_

    def getcorePoint(self,n_clusters_,labels):
        CorePoints = np.zeros((n_clusters_,3))
        CoreNum = np.zeros((n_clusters_))
        CoreSum = np.zeros((n_clusters_,3))
        Index = self.data.index[0]
        for point in range(0,len(self.data)):
            if labels[point] != -1:
                CoreNum[labels[point]] = CoreNum[labels[point]] + 1
                CoreSum[labels[point]][0] = CoreSum[labels[point]][0] + self.data.loc[point+Index].iat[3]
                CoreSum[labels[point]][1] = CoreSum[labels[point]][1] + self.data.loc[point+Index].iat[4]
                CoreSum[labels[point]][2] = CoreSum[labels[point]][2] + self.data.loc[point+Index].iat[5]

        for corepoint_id in range(0,n_clusters_):
            CorePoints[corepoint_id] = CoreSum[corepoint_id]/CoreNum[corepoint_id]
        return CorePoints
    
    def updatecluster(self,CorePoints,Next_Cluster_dict,n_clusters_, Frame_time, Distance, client1, client2):
        id1 = client1.ClusterID
        id2 = client2.ClusterID
        Cluster_dict = Next_Cluster_dict.copy()
        print(f'lol:{Cluster_dict}')
        Next_Cluster_dict = {}
        print(f'corepoints:{CorePoints}')
        Next_Velocity_dict = {}
	
        Threshold = {0:10,1:10,2:10,3:10,4:10,5:10,6:10,7:10,8:10,9:10,10:10,11:10,12:10,13:10,14:10,15:10}
        
        if Cluster_dict:
            if Distance == True:
                Min_dis = 100
                Min_key = 100
                for corepoint_id in range (0,n_clusters_):
                    dis = (Cluster_dict[id1][0]-CorePoints[corepoint_id][0])**2+(Cluster_dict[id1][1]-CorePoints[corepoint_id][1])**2\
                            +(Cluster_dict[id1][2]-CorePoints[corepoint_id][2])**2
                    if dis < Min_dis:
                        Min_key = corepoint_id
                        Min_dis = dis
                core1 = Min_key
                print(f'Minkey:{Min_key}')
                Next_Cluster_dict[id1] = CorePoints[Min_key]
                Min_dis = 100
                Min_key = 100
                for corepoint_id in range (0,n_clusters_):
                    if corepoint_id != core1:
                        dis = (Cluster_dict[id2][0]-CorePoints[corepoint_id][0])**2+(Cluster_dict[id2][1]-CorePoints[corepoint_id][1])**2\
                                +(Cluster_dict[id2][2]-CorePoints[corepoint_id][2])**2
                        if dis < Min_dis:
                            Min_key = corepoint_id
                            Min_dis = dis

                Next_Cluster_dict[id2] = CorePoints[Min_key]





            else:
                if len(Cluster_dict) >= n_clusters_:
                    for corepoint_id in range (0,n_clusters_):
                        Min_dis = 100
                        Min_key = 100
                        for keys in Cluster_dict:
                            dis = (Cluster_dict[keys][0]-CorePoints[corepoint_id][0])**2+(Cluster_dict[keys][1]-CorePoints[corepoint_id][1])**2\
                                    +(Cluster_dict[keys][2]-CorePoints[corepoint_id][2])**2
                            if dis < Min_dis:
                                Min_key = keys
                                Min_dis = dis
                        if Min_dis < Threshold[Min_key]:
                            Next_Cluster_dict[Min_key] = CorePoints[corepoint_id]
                            Threshold[Min_key] = Min_dis
                elif len(Cluster_dict) < n_clusters_:
                    for keys in Cluster_dict:
                        Min_dis = 100
                        Min_core_id = 100
                        for corepoint_id in range(0,n_clusters_):
                            if corepoint_id not in Next_Cluster_dict.keys():
                                dis = (Cluster_dict[keys][0]-CorePoints[corepoint_id][0])**2+(Cluster_dict[keys][1]-CorePoints[corepoint_id][1])**2\
                                        +(Cluster_dict[keys][2]-CorePoints[corepoint_id][2])**2
                                if dis < Min_dis:
                                    Min_core_id = corepoint_id
                                    Min_dis = dis
                        if Min_dis < Threshold[Min_core_id]:
                            Next_Cluster_dict[keys] = CorePoints[Min_core_id]
                            Threshold[Min_core_id] = Min_dis

                for keys in Cluster_dict:
                    if keys in Next_Cluster_dict:
                        Next_Velocity_dict[keys] = [(Next_Cluster_dict[keys][0] - Cluster_dict[keys][0]) / Frame_time,
                                                (Next_Cluster_dict[keys][1] - Cluster_dict[keys][1]) / Frame_time,
                                                (Next_Cluster_dict[keys][2] - Cluster_dict[keys][2]) / Frame_time]
            
        else:
            for corepoint_id in range(0,n_clusters_):
                Next_Cluster_dict[corepoint_id] = CorePoints[corepoint_id]
        print(f'Next_Cluster_dict: {Next_Cluster_dict}')
        return Cluster_dict, Next_Cluster_dict, Next_Velocity_dict
    
    def findrouter(self, client1, client2, Next_Velocity_dict, Next_Cluster_dict, distance):

        D = {}
        if distance == True:
            for keys in Next_Cluster_dict:
                D[norm(Next_Cluster_dict[keys][0]**2+Next_Cluster_dict[keys][1]**2)] = keys
            sortedD = sorted(D)
            print(f'D:{D}')
            print(f'sortedD:{sortedD}')
            client1.ClusterID = D[sortedD[0]]
            client2.ClusterID = D[sortedD[1]]


        else:
            r1 = [client1.x_velocity, client1.y_velocity, client1.z_velocity]
            r2 = [client2.x_velocity, client2.y_velocity, client2.z_velocity]
            #q = client.quaternion
            #print(f'before correction:{r}')
            #New_r = Direction_Correction(r,q)
            #client.x_velocity = New_r[0]
            #client.y_velocity = New_r[1]
            #client.z_velocity = New_r[2]
            #print(f'iframe: {client.imuFrame}')
            ###find the router###
            Min = 10000
            Min_id = 10000
            for keys in Next_Velocity_dict:
                dis =  (Next_Velocity_dict[keys][0]-r1[0])**2+(Next_Velocity_dict[keys][1]-r1[1])**2+(Next_Velocity_dict[keys][2]-r1[2])**2
                print(f'Distance: {dis}\n r1: {r1}')
                print(f'NVDict: {Next_Velocity_dict}')
                if dis < Min:
                    Min_id = keys
                    Min = dis

            client1.ClusterID = Min_id

            Min = 10000
            Min_id = 10000
            for keys in Next_Velocity_dict:
                if keys != client1.ClusterID:
                    dis =  (Next_Velocity_dict[keys][0]-r2[0])**2+(Next_Velocity_dict[keys][1]-r2[1])**2+(Next_Velocity_dict[keys][2]-r2[2])**2
                    print(f'Distance: {dis}\n r2: {r2}')
                    print(f'NVDict: {Next_Velocity_dict}')
                    if dis < Min:
                        Min_id = keys
                        Min = dis

            client2.ClusterID = Min_id

 
        return client1.ClusterID, client2.ClusterID

    def kalmanFilter(self,client,Next_Cluster_dict,KalmanMeasurements,KalmanP,Innovation,KalmanF,ConditionalX,ConditionalP):
        client_id = client.ClusterID
        SigmaInput = 1
        SigmaNoise = 0.5
        Delta = 0.5
        F = np.array([[1,0,Delta,0],[0,1,0,Delta],[0,0,1,0],[0,0,0,1]])
        Q = SigmaInput**2 * np.array([[Delta**3/3,0,Delta**2/2,0],
        [0,Delta**3/3,0,Delta**2/2],
        [Delta**2/2,0,Delta,0],
        [0,Delta**2/2,0,Delta]])
        H = np.array([[1,0,0,0],[0,1,0,0]])
        R = SigmaNoise**2 * np.identity(2)

        NoisyMeasurements = np.zeros((2,1))
        NoisyMeasurements[0,:] = Next_Cluster_dict[client_id][0]
        NoisyMeasurements[1,:] = Next_Cluster_dict[client_id][1]

        Innovation = NoisyMeasurements-H@ConditionalX
        KalmanF = ConditionalP@np.transpose(H)@np.linalg.inv(H@ConditionalP@np.transpose(H)+R)
        KalmanMeasurements = ConditionalX+KalmanF@Innovation
        KalmanP = ConditionalP-KalmanF@H@ConditionalP
        ConditionalX=F@KalmanMeasurements
        ConditionalP=F@KalmanP@np.transpose(F)+Q

        #client_imu_data = client.imuFrame
        client.x = KalmanMeasurements[0]
        client.y = KalmanMeasurements[1]
        
        return KalmanMeasurements,KalmanP,Innovation,KalmanF,ConditionalX,ConditionalP
		# estimate x,y leveraging imu data

 
    def getEstimate(self, client1, client2):
        ## Calculates the Direction (in radian, between 0 and 360) of client2 wrt client 1
        ratio = (client2.y-client1.y)/(client2.x-client1.x+0.000001)
        Theta = np.arctan(ratio)
        if client2.x-client1.x < 0:
            Theta = Theta + math.pi
        return Theta
