import { Route, Routes } from 'react-router-dom'
import AuthProvider from './auth/AuthProvider'
import RutaProtegida from './auth/RutaProtegida'
import Layout from './componentes/Layout'
import Marcador from './componentes/Marcador'
import Login from './paginas/Login'
import MapaMental from './paginas/MapaMental'
import Proyecto from './paginas/Proyecto'
import Usuarios from './paginas/Usuarios'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Proyecto />} />
          <Route path="login" element={<Login />} />
          <Route
            path="portafolio"
            element={
              <RutaProtegida>
                <Marcador titulo="Portafolio" requisito="RF-01, RF-02, RF-03" descripcion="Entrega de laboratorios por estudiante, cohorte y actividad, con versionado de rúbrica." />
              </RutaProtegida>
            }
          />
          <Route
            path="rubricas"
            element={
              <RutaProtegida roles={['docente', 'admin']}>
                <Marcador titulo="Rúbricas" requisito="RF-04, RF-05" descripcion="Carga, interpretación, edición y validación de rúbricas." />
              </RutaProtegida>
            }
          />
          <Route
            path="revision"
            element={
              <RutaProtegida roles={['docente', 'admin']}>
                <Marcador titulo="Revisión docente" requisito="RF-06, RF-07, RF-08" descripcion="Evaluación por criterio, nota preliminar y aprobación del docente." />
              </RutaProtegida>
            }
          />
          <Route
            path="informe"
            element={
              <RutaProtegida>
                <Marcador titulo="Informe integral" requisito="RF-09" descripcion="Informe de aprendizaje de ambas cohortes, descargable en PDF." />
              </RutaProtegida>
            }
          />
          <Route
            path="mapa-mental"
            element={
              <RutaProtegida>
                <MapaMental />
              </RutaProtegida>
            }
          />
          <Route
            path="usuarios"
            element={
              <RutaProtegida roles={['admin']}>
                <Usuarios />
              </RutaProtegida>
            }
          />
          <Route path="*" element={<Marcador titulo="Página no encontrada" requisito="404" descripcion="La ruta solicitada no existe." />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
