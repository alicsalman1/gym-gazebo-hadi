##Author Saurabh Nair; snnair@andrew.cmu.edu
import numpy as np
import copy as cp
import tf 

class reward_function:
  
    #def __init__(self, state_1, state_2, action_taken, dt, start_state, goal_state):
    def __init__(self, state_1, state_2):
        self.current_state = cp.deepcopy(state_2)
        self.previous_state = cp.deepcopy(state_1)
        #self.action = action_taken
        #self.goal_state = goal_state
        #self.start_state = start_state

	self.w_slip         = 0
	self.w_control      = 0
	self.w_collision    = 0
	self.w_energy       = 0	
	self.w_contact      = 0
	self.w_movement     = 1
	self.w_acceleration = 0
	self.alpha = 10
	#self.gamma = 1
	self.gamma = 0.5
	self.min_input_control = 0.005 ##Change in joint angles
	###Weights to each function
	self.any_movement_threshold = 0.05
    #State is arranged as:
    #Joint angles(18), Joint velocities(18), Joint Torques(),  Force-feedback(), IMU pose(3DOF +  4quat), bot pose(7)
    #current_state
    #previous_state
    def get_movement_direction(self):
	#import pdb
	#pdb.set_trace()

	trans1 =  self.previous_state.robot_pose[0][:3]
	trans1_mat = tf.transformations.translation_matrix(trans1)
	rot1 = self.previous_state.robot_pose[0][3:]
	rot1_mat   = tf.transformations.quaternion_matrix(rot1)
	mat1 = np.dot(trans1_mat, rot1_mat)
	
	trans2 =  self.current_state.robot_pose[0][:3]
	trans2_mat = tf.transformations.translation_matrix(trans2)
	rot2 = self.current_state.robot_pose[0][3:]
	rot2_mat   = tf.transformations.quaternion_matrix(rot2)
	mat2 = np.dot(trans2_mat, rot2_mat)
	
	mat3 = np.dot(mat1,np.linalg.inv(mat2))
	trans3 = tf.transformations.translation_from_matrix(mat3)
	rot3 = tf.transformations.quaternion_from_matrix(mat3)
	#print trans3
	return trans3
	
    def forward_movement(self):
	
        pos1 = np.array([self.previous_state.robot_pose[0][0],self.previous_state.robot_pose[0][1]])
	
        pos2 = np.array([self.current_state.robot_pose[0][0],self.current_state.robot_pose[0][1]])
	v = pos2 - pos1
	theta = np.arctan2(v[1],v[0])
	#import pdb
	#pdb.set_trace()
	if theta >  0 :
	    return -1
	else:
	    return 1

    def forward_acceleration(self):

	#This threshold has to be decided!
	snap_point = 2

        forward_acceleration = np.sqrt(np.square(self.current_state.imu_state[8]) + np.square(self.current_state.imu_state[9]))       
        #slow_down_point = np.norm(self.current_state.robot_state[0:3], self.goal_state[0:3]) > snap_point

	slow_down_point = 1
	if(slow_down_point):
		reward_acceleration = forward_acceleration
	else:
		reward_acceleration = -forward_acceleration #Promote deceleration at point close to the goal!
        return reward_acceleration

    #Not being used currently
    def any_movement(self):
        pos1 = self.previous_state.robot_pose[0]
        pos1 = np.array([self.previous_state.robot_pose[0][0],self.previous_state.robot_pose[0][1]])
	
        pos2 = np.array([self.current_state.robot_pose[0][0],self.current_state.robot_pose[0][1]])
	#v = pos2 - pos1
	disp = np.sqrt(np.sum(np.square(pos2 - pos1)))
	

	#This is going to cause some non-linearity in the reward function fitting!
	if(disp < self.any_movement_threshold):
		print "NO Movement"
		return -0.5
	else:
		return 0.5
		
	return self.w_movement*disp
         
    #Check for ground contact for each leg 
    def ground_contact(self):
        if(np.sum(self.current_state.end_effector_z[0:6] < 0.2) >= 2):
            a = self.w_contact*100
	else:
	    a =  self.w_contact*-100
	return a

    #Periodicity: Try to maintain (consume) the same energy every state
    def conservation_of_energy(self):
	#import pdb
	#pdb.set_trace()
	current_pose  = self.current_state.robot_pose[0]
	current_pose.extend(self.current_state.robot_pose[1])
	
        previous_pose = self.previous_state.robot_pose[0]
	previous_pose.extend(self.previous_state.robot_pose[1])
	current_pose = np.asarray(current_pose)
	previous_pose = np.asarray(previous_pose)
	diff_sq = np.absolute(current_pose- previous_pose)
	velocity_now = np.multiply(diff_sq[0:3], diff_sq[0:3])
	
 	#print velocity_now - velocity_previous
	accelerations = np.multiply(self.current_state.imu_state[7:10],self.current_state.imu_state[7:10])
	energy_each = np.multiply(accelerations,velocity_now)	
	total_energy = np.sum(energy_each)

	if total_energy <= 0:
		total_energy = 0.01
	return total_energy
	
	
    #polygon of support
    def static_stability(self):
	return 1

    #Fucking add a penalty if the robot hits itself
    def self_collision(self):
	
        #if(self.current_state.collision):
         #  return -1000
        #else:
        return 10
        
    #To have minimum energy added to the system
    def control_input(self):
	#import pdb
	#pdb.set_trace()
	prev_joint_positions = cp.deepcopy(self.previous_state.joint_positions)
	current_joint_positions = cp.deepcopy(self.current_state.joint_positions)
	u = np.sqrt(np.sum(np.square(current_joint_positions - prev_joint_positions)))
	return u
    #Add reward for being normal to the surface
    def slip_avoidance(self):
	angles = self.current_state.end_effector_angles
	contacts = (self.current_state.end_effector_z[0:6] < 0.2)

	normal_index = 0
	total_error = 0
	for limb in range(6):
	    if(contacts[limb]):
	        contact_angle =  angles[3*limb:3*limb + 3]
		diff = contact_angle[normal_index] - np.pi
		total_error = total_error + diff*diff
	if total_error == 0 :
		total_error = 0.01
	return total_error

    def total_reward(self):
	trans = self.get_movement_direction()
	u_sig = self.control_input()
	lazy_penalty = 0
	print u_sig
	if(u_sig < self.min_input_control):
		print "LAzy`"
		lazy_penalty = -2

		
	return self.alpha*(trans[1] - self.any_movement_threshold) - self.gamma*u_sig + lazy_penalty 
	#return (self.w_slip)/self.slip_avoidance() + self.w_control/self.control_input() + self.w_collision/self.self_collision() + self.w_energy/self.conservation_of_energy() + self.w_contact*self.ground_contact() + self.w_movement*self.any_movement() + self.w_acceleration*self.forward_acceleration()
