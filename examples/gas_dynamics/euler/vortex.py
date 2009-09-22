# Hedge - the Hybrid'n'Easy DG Environment
# Copyright (C) 2008 Andreas Kloeckner
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.




from __future__ import division
import numpy
import numpy.linalg as la




class Vortex:
    def __init__(self):
        self.beta = 5
        self.gamma = 1.4
        self.center = numpy.array([5, 0])
        self.velocity = numpy.array([1, 0])

        self.mu = 0
        self.prandtl = 0.72
        self.spec_gas_const = 287.1

    def __call__(self, t, x_vec):
        vortex_loc = self.center + t*self.velocity

        # coordinates relative to vortex center
        x_rel = x_vec[0] - vortex_loc[0]
        y_rel = x_vec[1] - vortex_loc[1]

        # Y.C. Zhou, G.W. Wei / Journal of Computational Physics 189 (2003) 159
        # also JSH/TW Nodal DG Methods, p. 209

        from math import pi
        r = numpy.sqrt(x_rel**2+y_rel**2)
        expterm = self.beta*numpy.exp(1-r**2)
        u = self.velocity[0] - expterm*y_rel/(2*pi)
        v = self.velocity[1] + expterm*x_rel/(2*pi)
        rho = (1-(self.gamma-1)/(16*self.gamma*pi**2)*expterm**2)**(1/(self.gamma-1))
        p = rho**self.gamma

        e = p/(self.gamma-1) + rho/2*(u**2+v**2)

        from hedge.tools import join_fields
        return join_fields(rho, e, rho*u, rho*v)

    def properties(self):
        return(self.gamma, self.mu, self.prandtl, self.spec_gas_const)


    def volume_interpolant(self, t, discr):
        return discr.convert_volume(
			self(t, discr.nodes.T
                            .astype(discr.default_scalar_type)),
			kind=discr.compute_kind)

    def boundary_interpolant(self, t, discr, tag):
        return discr.convert_boundary(
			self(t, discr.get_boundary(tag).nodes.T
                            .astype(discr.default_scalar_type)),
			 tag=tag, kind=discr.compute_kind)




def main(write_output=True):
    from hedge.backends import guess_run_context
    rcon = guess_run_context(
		    #["cuda"]
		    )

    from hedge.tools import EOCRecorder, to_obj_array
    eoc_rec = EOCRecorder()

    if rcon.is_head_rank:
        from hedge.mesh import \
                make_rect_mesh, \
                make_centered_regular_rect_mesh

        refine = 1
        mesh = make_centered_regular_rect_mesh((0,-5), (10,5), n=(9,9),
                post_refine_factor=refine)
        mesh_data = rcon.distribute_mesh(mesh)
    else:
        mesh_data = rcon.receive_mesh()

    for order in [3, 4, 5]:
        discr = rcon.make_discretization(mesh_data, order=order,
			default_scalar_type=numpy.float64)

        from hedge.visualization import SiloVisualizer, VtkVisualizer
        #vis = VtkVisualizer(discr, rcon, "vortex-%d" % order)
        vis = SiloVisualizer(discr, rcon)

        vortex = Vortex()
        fields = vortex.volume_interpolant(0, discr)
        gamma, mu, prandtl, spec_gas_const = vortex.properties()

        from hedge.models.gas_dynamics import GasDynamicsOperator
        from hedge.mesh import TAG_ALL
        op = GasDynamicsOperator(dimensions=2, discr=discr, gamma=gamma, mu=mu,
                prandtl=prandtl, spec_gas_const=spec_gas_const,
                bc_inflow=vortex, bc_outflow=vortex, bc_noslip=vortex,
                inflow_tag=TAG_ALL, euler=True)

        euler_ex = op.bind(discr)

        max_eigval = [0]
        def rhs(t, q):
            ode_rhs, speed = euler_ex(t, q)
            max_eigval[0] = speed
            return ode_rhs
        rhs(0, fields)

        dt = discr.dt_factor(max_eigval[0])
        final_time = 0.6
        nsteps = int(final_time/dt)+1
        dt = final_time/nsteps

        if rcon.is_head_rank:
            print "---------------------------------------------"
            print "order %d" % order
            print "---------------------------------------------"
            print "dt", dt
            print "nsteps", nsteps
            print "#elements=", len(mesh.elements)

        from hedge.timestep import RK4TimeStepper
        stepper = RK4TimeStepper()

        # diagnostics setup ---------------------------------------------------
        from pytools.log import LogManager, add_general_quantities, \
                add_simulation_quantities, add_run_info

        if write_output:
            log_file_name = "euler-%d.dat" % order
        else:
            log_file_name = None

        logmgr = LogManager(log_file_name, "w", rcon.communicator)
        add_run_info(logmgr)
        add_general_quantities(logmgr)
        add_simulation_quantities(logmgr, dt)
        discr.add_instrumentation(logmgr)
        stepper.add_instrumentation(logmgr)

        logmgr.add_watches(["step.max", "t_sim.max", "t_step.max"])

        # timestep loop -------------------------------------------------------
        t = 0

        try:
            for step in range(nsteps):
                logmgr.tick()

                if step % 1 == 0 and write_output:
                #if False:
                    visf = vis.make_file("vortex-%d-%04d" % (order, step))

                    true_fields = vortex.volume_interpolant(t, discr)

                    from pylo import DB_VARTYPE_VECTOR
                    vis.add_data(visf,
                            [
                                ("rho", discr.convert_volume(op.rho(fields), kind="numpy")),
                                ("e", discr.convert_volume(op.e(fields), kind="numpy")),
                                ("rho_u", discr.convert_volume(op.rho_u(fields), kind="numpy")),
                                ("u", discr.convert_volume(op.u(fields), kind="numpy")),

                                #("true_rho", discr.convert_volume(op.rho(true_fields), kind="numpy")),
                                #("true_e", discr.convert_volume(op.e(true_fields), kind="numpy")),
                                #("true_rho_u", discr.convert_volume(op.rho_u(true_fields), kind="numpy")),
                                #("true_u", discr.convert_volume(op.u(true_fields), kind="numpy")),

                                #("rhs_rho", discr.convert_volume(op.rho(rhs_fields), kind="numpy")),
                                #("rhs_e", discr.convert_volume(op.e(rhs_fields), kind="numpy")),
                                #("rhs_rho_u", discr.convert_volume(op.rho_u(rhs_fields), kind="numpy")),
                                ],
                            expressions=[
                                #("diff_rho", "rho-true_rho"),
                                #("diff_e", "e-true_e"),
                                #("diff_rho_u", "rho_u-true_rho_u", DB_VARTYPE_VECTOR),

                                ("p", "0.4*(e- 0.5*(rho_u*u))"),
                                ],
                            time=t, step=step
                            )
                    visf.close()

                fields = stepper(fields, t, dt, rhs)
                t += dt

                dt = discr.dt_factor(max_eigval[0])
            logmgr.tick()

            true_fields = vortex.volume_interpolant(t, discr)
            l2_error = discr.norm(fields-true_fields)
            l2_error_rho = discr.norm(op.rho(fields)-op.rho(true_fields))
            l2_error_e = discr.norm(op.e(fields)-op.e(true_fields))
            l2_error_rhou = discr.norm(op.rho_u(fields)-op.rho_u(true_fields))
            l2_error_u = discr.norm(op.u(fields)-op.u(true_fields))

            eoc_rec.add_data_point(order, l2_error)
            print
            print eoc_rec.pretty_print("P.Deg.", "L2 Error")

            logmgr.set_constant("l2_error", l2_error)
            logmgr.set_constant("l2_error_rho", l2_error_rho)
            logmgr.set_constant("l2_error_e", l2_error_e)
            logmgr.set_constant("l2_error_rhou", l2_error_rhou)
            logmgr.set_constant("l2_error_u", l2_error_u)
            logmgr.set_constant("refinement", refine)

        finally:
            if write_output:
                vis.close()

            logmgr.save()

            discr.close()

    # after order loop
    assert eoc_rec.estimate_order_of_convergence()[0,1] > 6




if __name__ == "__main__":
    main()



# entry points for py.test ----------------------------------------------------
from pytools.test import mark_test
@mark_test.long
def test_euler_vortex():
    main()