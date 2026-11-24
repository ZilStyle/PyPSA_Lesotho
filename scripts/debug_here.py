import gurobipy as gp

m = gp.Model()

# Correct way to check license limits in Gurobi 13
x = m.addVar(name="x")
m.setObjective(x, gp.GRB.MINIMIZE)
m.addConstr(x >= 1)
m.optimize()
print("Test solve status:", m.Status)  # 2 = OPTIMAL

# Check license limits via environment
env = m.getEnv()
print("SizeLimit:", env.getParamInfo("SizeConstraint"))