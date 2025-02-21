from py4godot import *
import py4godot, math
from Scripts.Tools.Draw import *
from Scripts.Navigation.AStarPoint import AStarPoint
from typing import Optional, List, Dict, Set, Tuple
from Scripts.Navigation import NavigationUtils

WALKABLE_GROUP     = "walkable"
GRIDSIZE	       = 1
SCALE 		       = 1
DRAW_RAD 	       = 0.2
FLOAT_TOLERANCE	   = 0.1
WEIGHT_SCALE	   = 1

@gdclass
class AStar(Spatial, Draw):

	def __init__(self):
		# Don't call any godot-methods here
		super().__init__()
		self.astar: Optional[py4godot.AStar] = None
		self.walkables: Optional[Array] = None
		self.points:List = []
		self.dict_points:Dict = dict()
		self.utils_path:Optional[NodePath] = None
		self.utils:Optional[Spatial] = None
		self.push_obj_layer:int = 32
		self.disabled_points:List = []
		self.already_traced_pos:Set[Tuple[int, int, int]] = set()

	prop("utils_path", NodePath, NodePath())
	prop("push_obj_layer", int, 32)
	@gdmethod
	def _ready(self):
		self.astar = py4godot.AStar._new()
		self.walkables = self.get_tree().get_nodes_in_group(WALKABLE_GROUP)
		self.get_pyscript().method()
		#self.generate_points()

		self.utils = self.get_node(self.utils_path)

		#self.generate_point_connections()

		self.generate_points_advanced()
		self.generate_disabled()
		for point in self.points:
			self.draw_sphere(point.id, DRAW_RAD, point.position, color=Color(1,0,0) if point in self.disabled_points else Color(1,1,1))

	@gdmethod
	def _process(self, delta: float) ->None:
		for point in self.disabled_points:
			self.draw_sphere(point.id, DRAW_RAD, point.position,
							 color=Color(1,0,0) if point in self.disabled_points else Color(1,1,1))
	def method(self):
		print("method")

	def generate_points_advanced(self)->None:
		"""Here we use advanced generation to calculate points"""
		self.add_point(Vector3(0,GRIDSIZE/2,0),-1)

	def add_point(self, pos:Vector3, current_dir:int)->None:
		"""Recursive algorithm to run over all possible points."""
		if not self.point_below(pos) or (pos.x, pos.y, pos.z) in self.already_traced_pos:
			return
		self.already_traced_pos.add((pos.x, pos.y, pos.z))
		print("add_point:", pos.x, "|", pos.y, "|", pos.z)
		self.points.append(AStarPoint(pos.x / SCALE,
									  pos.y,
									  pos.z,
									  NavigationUtils.calc_point_id(pos.x // SCALE, pos.z // SCALE)))
		# TODO: convert this to enums
		if (current_dir != 0):
			self.add_point(Vector3(pos.x + GRIDSIZE, pos.y, pos.z), 1)
		if (current_dir != 1):
			self.add_point(Vector3(pos.x - GRIDSIZE, pos.y, pos.z), 0)
		if (current_dir != 2):
			self.add_point(Vector3(pos.x, pos.y, pos.z + GRIDSIZE),3)
		if (current_dir != 3):
			self.add_point(Vector3(pos.x, pos.y, pos.z - GRIDSIZE), 2)
	def point_below(self,pos:Vector3):
		"""Function for checking point below"""
		result = self.get_world().direct_space_state.intersect_ray(pos,
																   pos + Vector3(0,-1,0) * GRIDSIZE, Array(),
																   collision_mask=1)

		return result.size() > 0

	def generate_points(self)->None:
		"""Here we are generating all the points we could later use for astar"""
		for walkable in self.walkables:
			mesh: Optional[MeshInstance] = self.get_mesh(walkable)
			if (not mesh):
				continue
			aabb: AABB = mesh.get_transformed_aabb()
			self.generate_squares(aabb)

	def generate_squares(self, box_to_fill:AABB) -> None:
		""" Generate objects at matching points """
		id_counter:int = 0
		for x in range(int(box_to_fill.get_position().x * SCALE),
					   int((box_to_fill.get_position().x + box_to_fill.get_size().x)*SCALE),
					   int(GRIDSIZE * SCALE)):
			for z in range(int(box_to_fill.get_position().z * SCALE),
						   int((box_to_fill.get_position().z + box_to_fill.get_size().z)*SCALE),
						   int(GRIDSIZE * SCALE)):
				point:AStarPoint = AStarPoint(x / SCALE,
								   			  box_to_fill.get_position().y + box_to_fill.get_size().y,
											  z/SCALE,
								   			  NavigationUtils.calc_point_id(x//SCALE, z//SCALE))
				self.points.append(point)
				self.dict_points[point.id] = point
				self.astar.add_point(point.id, point.position, weight_scale=10.)
				id_counter += 1

		for point in self.points:
			self.immediate_geometry_init(self, point.id)
	def get_mesh(self, node:Node) -> Optional[MeshInstance]:
		"""This function is used to get a mesh child from a given Node"""
		for child in node.get_children():
			if isinstance(child, MeshInstance):
				return child


	def generate_point_connections(self)->None:
		"""Here we generate the connections between the points, the player can walk"""
		for point in self.points:
			for other_point in self.points:
				diff:Vector3 = point.position- other_point.position
				if diff.length() <= math.sqrt(2) * GRIDSIZE + FLOAT_TOLERANCE and other_point != point:
					self.astar.connect_points(point.id, other_point.id)
					point.connected_points.append(other_point)

	def generate_disabled(self)->None:
		for point in self.points:
			self.set_point_disabled(point)
	def set_point_disabled(self, point:AStarPoint)->None:
		erg: Variant = self.utils.callv("sphere_cast", Array(point.position,
				GRIDSIZE * math.sqrt(2),Array(self), self.push_obj_layer))

		disabled:bool = erg.get_converted_value().size() != 0

		self.astar.set_point_disabled(point.id, disabled=disabled)

	def disable_points(self, x_pos:int, z_pos:int, x_size:int, z_size:int )->None:

		for point in self.disabled_points:
			self.draw_sphere(point.id, DRAW_RAD, point.position)
			self.astar.set_point_disabled(point.id, False)
		self.disabled_points = []
		for x in range(round(x_pos-x_size/2.), round(x_pos+x_size/2. + 1),GRIDSIZE):
			for z in range(round(z_pos-z_size/2.), round(z_pos+z_size/2.+ 1),GRIDSIZE):
				point_id: int = NavigationUtils.calc_point_id(x, z)
				if point_id in self.dict_points.keys():
					self.astar.set_point_disabled(point_id, True)
					self.disabled_points.append(self.dict_points[point_id])
				else:
					print("point_to_disable_not_found:", point_id)

	@gdmethod
	def get_way_points(self, start_position:Vector3, end_position:Vector3)->PoolVector3Array:
		start = self.astar.get_closest_point(start_position)
		end = self.astar.get_closest_point(end_position)
		return self.astar.get_point_path(start, end)

