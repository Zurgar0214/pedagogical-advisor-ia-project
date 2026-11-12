import { Route, Routes } from 'react-router-dom'
import Layout from './componentes/Layout'
import Marcador from './componentes/Marcador'
import MapaMental from './paginas/MapaMental'
import Proyecto from './paginas/Proyecto'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Proyecto />} />
        <Route
          path="portafolio"
          element={<Marcador titulo="Portafolio" requisito="RF-01, RF-02, RF-03" descripcion="Entrega de laboratorios por estudiante, cohorte y actividad, con versionado de rúbrica." />}
        />
        <Route
          path="rubricas"
          element={<Marcador titulo="Rúbricas" requisito="RF-04, RF-05" descripcion="Carga, interpretación, edición y validación de rúbricas." />}
        />
        <Route
          path="revision"
          element={<Marcador titulo="Revisión docente" requisito="RF-06, RF-07, RF-08" descripcion="Evaluación por criterio, nota preliminar y aprobación del docente." />}
        />
        <Route
          path="informe"
          element={<Marcador titulo="Informe integral" requisito="RF-09" descripcion="Informe de aprendizaje de ambas cohortes, descargable en PDF." />}
        />
        <Route path="mapa-mental" element={<MapaMental />} />
        <Route
          path="login"
          element={<Marcador titulo="Iniciar sesión" requisito="Autenticación y roles" descripcion="Acceso por rol: estudiante o docente." />}
        />
        <Route path="*" element={<Marcador titulo="Página no encontrada" requisito="404" descripcion="La ruta solicitada no existe." />} />
      </Route>
    </Routes>
  )
}
